from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Generator, Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

try:
    import modal
except ImportError:  # Modal is optional for local contract tests.
    modal = None


APP_NAME = "cortex-lab-tribe-inference"
FUNCTION_NAME = "run"
TRIBE_MODEL_ID = "facebook/tribev2"
FAKE_VERTEX_COUNT = 16
FAKE_TIMESTEPS_PER_BLOCK = 1
DEFAULT_SAMPLE_RATE_HZ = 2
AUDIO_EXTENSIONS_BY_MIME = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
}
VIDEO_EXTENSIONS_BY_MIME = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


def _run_blocks(spec: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = spec.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("run spec must include at least one block")
    return blocks


def _sample_rate_hz(spec: dict[str, Any]) -> int:
    settings = spec.get("settings")
    if isinstance(settings, dict):
        sample_rate = settings.get("target_sample_rate_hz", DEFAULT_SAMPLE_RATE_HZ)
        if isinstance(sample_rate, int) and sample_rate > 0:
            return sample_rate
    return DEFAULT_SAMPLE_RATE_HZ


def build_fake_activation_matrix(
    *,
    chunk_index: int,
    timestep_count: int = FAKE_TIMESTEPS_PER_BLOCK,
    vertex_count: int = FAKE_VERTEX_COUNT,
) -> np.ndarray:
    if timestep_count <= 0:
        raise ValueError("timestep_count must be positive")
    if vertex_count <= 0:
        raise ValueError("vertex_count must be positive")

    values = np.arange(timestep_count * vertex_count, dtype=np.float32).reshape(timestep_count, vertex_count)
    return np.ascontiguousarray(values + np.float32(chunk_index / 1000), dtype="<f4")


def activation_chunk_event(
    *,
    job_id: str,
    block_id: str,
    chunk_index: int,
    timestep_start: int,
    sample_rate_hz: int,
    activations: np.ndarray,
) -> dict[str, Any]:
    matrix = np.asarray(activations, dtype="<f4")
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, matrix.shape[0])
    if matrix.ndim != 2:
        raise ValueError("activations must be a 1D or 2D float32 array")

    matrix = np.ascontiguousarray(matrix, dtype="<f4")
    timestep_count, vertex_count = matrix.shape
    return {
        "type": "chunk",
        "job_id": job_id,
        "block_id": block_id,
        "chunk_index": chunk_index,
        "timestep_start": timestep_start,
        "timestep_count": timestep_count,
        "sample_rate_hz": sample_rate_hz,
        "vertex_count": vertex_count,
        "dtype": "float32",
        "shape": [timestep_count, vertex_count],
        "activations": matrix.tobytes(order="C"),
    }


def run_fake_stream(spec: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    blocks = _run_blocks(spec)
    job_id = str(spec.get("job_id") or "modal-smoke")
    sample_rate_hz = _sample_rate_hz(spec)

    yield {
        "type": "warming",
        "job_id": job_id,
        "reason": "modal_fake_provider",
        "estimated_seconds": 1,
    }

    completed_timesteps = 0
    total_blocks = len(blocks)
    yield {
        "type": "progress",
        "job_id": job_id,
        "completed_blocks": 0,
        "total_blocks": total_blocks,
        "completed_timesteps": completed_timesteps,
    }

    for chunk_index, block in enumerate(blocks):
        block_id = str(block.get("id") or f"block-{chunk_index}")
        activations = build_fake_activation_matrix(chunk_index=chunk_index)
        yield activation_chunk_event(
            job_id=job_id,
            block_id=block_id,
            chunk_index=chunk_index,
            timestep_start=completed_timesteps,
            sample_rate_hz=sample_rate_hz,
            activations=activations,
        )

        completed_timesteps += activations.shape[0]
        yield {
            "type": "progress",
            "job_id": job_id,
            "completed_blocks": chunk_index + 1,
            "total_blocks": total_blocks,
            "completed_timesteps": completed_timesteps,
        }

    yield {
        "type": "complete",
        "job_id": job_id,
        "status": "complete",
        "timesteps": completed_timesteps,
        "vertex_count": FAKE_VERTEX_COUNT,
    }


@lru_cache(maxsize=1)
def load_tribe_model():
    try:
        from tribev2 import TribeModel
    except ImportError as exc:
        raise RuntimeError(
            "TRIBE v2 is not installed. Clone the official facebook/tribev2 repository and install it with "
            "`pip install -e .` before setting TRIBE_INFERENCE_MODE=real."
        ) from exc

    cache_folder = os.environ.get("TRIBE_CACHE_FOLDER", "./cache")
    return TribeModel.from_pretrained(TRIBE_MODEL_ID, cache_folder=cache_folder)


def _write_text_block(block: dict[str, Any], working_dir: Path) -> Path:
    text = block.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text blocks require non-empty text for TRIBE inference")

    path = working_dir / f"{block.get('id', 'text')}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _safe_file_stem(block: dict[str, Any], fallback: str) -> str:
    raw_id = str(block.get("id") or fallback)
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in raw_id)


def download_s3_object(*, bucket_name: str, key: str, destination: Path) -> Path:
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("boto3 is required to materialize S3 inputs for real TRIBE inference") from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    client = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
    client.download_file(bucket_name, key, str(destination))
    return destination


def _materialize_media_block(
    block: dict[str, Any],
    working_dir: Path,
    *,
    extensions_by_mime: dict[str, str],
    fallback_extension: str,
) -> Path:
    local_path = block.get("local_path")
    if isinstance(local_path, str) and local_path:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"local input file does not exist: {path}")
        return path

    s3_key = block.get("s3_key")
    if not isinstance(s3_key, str) or not s3_key:
        raise ValueError("real TRIBE media blocks require local_path or s3_key")

    bucket_name = os.environ.get("S3_BUCKET_NAME")
    if not bucket_name:
        raise ValueError("S3_BUCKET_NAME is required to materialize S3 inputs")

    mime_type = str(block.get("mime_type") or "")
    extension = extensions_by_mime.get(mime_type, fallback_extension)
    destination = working_dir / "inputs" / f"{_safe_file_stem(block, 'media')}{extension}"
    return download_s3_object(bucket_name=bucket_name, key=s3_key, destination=destination)


def _events_dataframe_for_block(model: Any, block: dict[str, Any], working_dir: Path) -> Any:
    block_type = block.get("type")
    if block_type == "text":
        text_path = _write_text_block(block, working_dir)
        return model.get_events_dataframe(text_path=str(text_path))
    if block_type == "audio":
        audio_path = _materialize_media_block(
            block,
            working_dir,
            extensions_by_mime=AUDIO_EXTENSIONS_BY_MIME,
            fallback_extension=".wav",
        )
        return model.get_events_dataframe(audio_path=str(audio_path))
    if block_type == "video":
        video_path = _materialize_media_block(
            block,
            working_dir,
            extensions_by_mime=VIDEO_EXTENSIONS_BY_MIME,
            fallback_extension=".mp4",
        )
        return model.get_events_dataframe(video_path=str(video_path))

    raise ValueError(
        "Real TRIBE inference supports official text_path, audio_path, and video_path inputs. "
        "Image blocks need a documented conversion decision before real TRIBE inference."
    )


def run_real_tribe_stream(
    spec: dict[str, Any],
    *,
    model: Any | None = None,
    working_dir: Path | None = None,
) -> Generator[dict[str, Any], None, None]:
    blocks = _run_blocks(spec)
    job_id = str(spec.get("job_id") or "tribe-real")
    sample_rate_hz = _sample_rate_hz(spec)

    yield {
        "type": "warming",
        "job_id": job_id,
        "reason": "tribe_model_loading",
        "estimated_seconds": 120,
    }

    model = model or load_tribe_model()
    completed_timesteps = 0
    total_blocks = len(blocks)
    vertex_count = 0

    yield {
        "type": "progress",
        "job_id": job_id,
        "completed_blocks": 0,
        "total_blocks": total_blocks,
        "completed_timesteps": completed_timesteps,
    }

    temp_context = None
    if working_dir is None:
        temp_context = tempfile.TemporaryDirectory(prefix="cortex-tribe-")
        working_dir = Path(temp_context.name)
    else:
        working_dir.mkdir(parents=True, exist_ok=True)

    try:
        for chunk_index, block in enumerate(blocks):
            block_id = str(block.get("id") or f"block-{chunk_index}")
            events = _events_dataframe_for_block(model, block, working_dir)
            predictions, _segments = model.predict(events=events)
            activations = np.asarray(predictions, dtype="<f4")
            if activations.ndim != 2:
                raise ValueError("TRIBE predictions must have shape (n_timesteps, n_vertices)")

            vertex_count = int(activations.shape[1])
            yield activation_chunk_event(
                job_id=job_id,
                block_id=block_id,
                chunk_index=chunk_index,
                timestep_start=completed_timesteps,
                sample_rate_hz=sample_rate_hz,
                activations=activations,
            )

            completed_timesteps += int(activations.shape[0])
            yield {
                "type": "progress",
                "job_id": job_id,
                "completed_blocks": chunk_index + 1,
                "total_blocks": total_blocks,
                "completed_timesteps": completed_timesteps,
            }
    finally:
        if temp_context is not None:
            temp_context.cleanup()

    yield {
        "type": "complete",
        "job_id": job_id,
        "status": "complete",
        "timesteps": completed_timesteps,
        "vertex_count": vertex_count,
    }


def run_configured_stream(spec: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
    mode = os.environ.get("TRIBE_INFERENCE_MODE", "fake").strip().lower()
    if mode == "fake":
        yield from run_fake_stream(spec)
        return
    if mode == "real":
        yield from run_real_tribe_stream(spec)
        return
    raise ValueError(f"Unsupported TRIBE_INFERENCE_MODE: {mode}")


def _json_safe_event(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("type") != "chunk":
        return event
    safe_event = dict(event)
    safe_event["activation_bytes"] = len(event["activations"])
    safe_event.pop("activations", None)
    return safe_event


def _smoke_spec() -> dict[str, Any]:
    return {
        "job_id": "modal-smoke",
        "blocks": [
            {
                "id": "image-1",
                "type": "image",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "s3_key": "dev/image.png",
                "mime_type": "image/png",
            },
            {
                "id": "text-1",
                "type": "text",
                "start_ms": 1000,
                "duration_ms": 1000,
                "content_hash": "sha256:def456",
                "text": "Cortex Lab smoke test",
            },
        ],
        "settings": {
            "target_sample_rate_hz": DEFAULT_SAMPLE_RATE_HZ,
            "surface": "fsaverage5",
            "atlas": "desikan-killiany",
        },
    }


def _print_smoke_events(events: Iterable[dict[str, Any]]) -> None:
    for event in events:
        print(json.dumps(_json_safe_event(event), sort_keys=True))


if modal is not None:
    image = modal.Image.debian_slim(python_version="3.11").pip_install(
        "numpy==2.2.1",
        "msgpack==1.1.0",
    )
    app = modal.App(APP_NAME)

    @app.function(image=image, gpu="A10G", timeout=300)
    def run(spec: dict[str, Any]):
        yield from run_configured_stream(spec)

else:
    app = None


def main() -> None:
    parser = argparse.ArgumentParser(description="TRIBE inference Modal scaffold")
    parser.add_argument("--smoke", action="store_true", help="run the local fake stream contract smoke test")
    args = parser.parse_args()

    if args.smoke:
        _print_smoke_events(run_fake_stream(_smoke_spec()))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
