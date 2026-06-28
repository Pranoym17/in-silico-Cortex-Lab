from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
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
OFFICIAL_TRIBE_SOURCE_URL = "git+https://github.com/facebookresearch/tribev2.git"
COMPATIBLE_EXCA_VERSION = "0.5.20"
COMPATIBLE_TRANSFORMERS_VERSION = "4.48.3"
FAKE_VERTEX_COUNT = 16
FAKE_TIMESTEPS_PER_BLOCK = 1
DEFAULT_SAMPLE_RATE_HZ = 2
DEFAULT_REAL_CHUNK_TIMESTEPS = 4
FSAVERAGE5_VERTEX_COUNT = 20484
TRIBE_HRF_OFFSET_SECONDS = 5.0
IMAGE_EXTENSIONS_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
AUDIO_EXTENSIONS_BY_MIME = {
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/webm": ".webm",
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


def _real_chunk_timesteps() -> int:
    raw_value = os.environ.get("TRIBE_CHUNK_TIMESTEPS", str(DEFAULT_REAL_CHUNK_TIMESTEPS))
    try:
        chunk_timesteps = int(raw_value)
    except ValueError as exc:
        raise ValueError("TRIBE_CHUNK_TIMESTEPS must be an integer") from exc
    if chunk_timesteps <= 0:
        raise ValueError("TRIBE_CHUNK_TIMESTEPS must be positive")
    return chunk_timesteps


def _expected_vertex_count() -> int | None:
    raw_value = os.environ.get("TRIBE_EXPECTED_VERTEX_COUNT", "").strip()
    if not raw_value:
        return None
    try:
        vertex_count = int(raw_value)
    except ValueError as exc:
        raise ValueError("TRIBE_EXPECTED_VERTEX_COUNT must be an integer") from exc
    if vertex_count <= 0:
        raise ValueError("TRIBE_EXPECTED_VERTEX_COUNT must be positive")
    return vertex_count


def _modal_secret_name() -> str:
    return os.environ.get("MODAL_HF_SECRET_NAME", "huggingface-secret").strip() or "huggingface-secret"


def _real_tribe_env() -> dict[str, str]:
    return {
        "TRIBE_INFERENCE_MODE": "real",
        "TRIBE_CACHE_FOLDER": "/cache",
        "TRIBE_CHUNK_TIMESTEPS": os.environ.get("TRIBE_CHUNK_TIMESTEPS", str(DEFAULT_REAL_CHUNK_TIMESTEPS)),
        "TRIBE_EXPECTED_VERTEX_COUNT": os.environ.get(
            "TRIBE_EXPECTED_VERTEX_COUNT",
            str(FSAVERAGE5_VERTEX_COUNT),
        ),
    }


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


def iter_activation_chunks(
    *,
    activations: np.ndarray,
    chunk_timesteps: int,
) -> Generator[tuple[int, np.ndarray], None, None]:
    matrix = np.asarray(activations, dtype="<f4")
    if matrix.ndim != 2:
        raise ValueError("activation matrix must have shape (n_timesteps, n_vertices)")
    if chunk_timesteps <= 0:
        raise ValueError("chunk_timesteps must be positive")

    timestep_count = matrix.shape[0]
    for timestep_start in range(0, timestep_count, chunk_timesteps):
        yield timestep_start, np.ascontiguousarray(matrix[timestep_start : timestep_start + chunk_timesteps], dtype="<f4")


def validate_prediction_matrix(
    predictions: Any,
    *,
    expected_vertex_count: int | None,
) -> np.ndarray:
    activations = np.asarray(predictions, dtype="<f4")
    if activations.ndim != 2:
        raise ValueError("TRIBE predictions must have shape (n_timesteps, n_vertices)")
    if activations.shape[0] <= 0:
        raise ValueError("TRIBE predictions must include at least one timestep")
    if activations.shape[1] <= 0:
        raise ValueError("TRIBE predictions must include at least one vertex")
    if expected_vertex_count is not None and activations.shape[1] != expected_vertex_count:
        raise ValueError(
            f"TRIBE predicted {activations.shape[1]} vertices, but TRIBE_EXPECTED_VERTEX_COUNT="
            f"{expected_vertex_count}. Check mesh/output ordering before rendering."
        )
    return np.ascontiguousarray(activations, dtype="<f4")


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


def check_real_tribe_config(spec: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = spec or {}
    blocks = spec.get("blocks") if isinstance(spec.get("blocks"), list) else []
    media_blocks = [
        block for block in blocks if isinstance(block, dict) and block.get("type") in {"image", "audio", "video"}
    ]
    s3_media_blocks = [block for block in media_blocks if block.get("s3_key") and not block.get("local_path")]
    image_blocks = [block for block in blocks if isinstance(block, dict) and block.get("type") == "image"]

    checks = {
        "tribe_package_available": importlib.util.find_spec("tribev2") is not None,
        "modal_package_available": modal is not None,
        "hf_token_present": bool(os.environ.get("HF_TOKEN")),
        "s3_bucket_present": bool(os.environ.get("S3_BUCKET_NAME")),
        "aws_region_present": bool(os.environ.get("AWS_REGION")),
        "chunk_timesteps_valid": True,
        "expected_vertex_count_valid": True,
        "requires_s3_materialization": bool(s3_media_blocks),
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
    }

    try:
        _real_chunk_timesteps()
    except ValueError:
        checks["chunk_timesteps_valid"] = False

    try:
        _expected_vertex_count()
    except ValueError:
        checks["expected_vertex_count_valid"] = False

    blockers = []
    warnings = []
    if not checks["tribe_package_available"]:
        blockers.append("TRIBE v2 package is not installed")
    if not checks["chunk_timesteps_valid"]:
        blockers.append("TRIBE_CHUNK_TIMESTEPS must be a positive integer")
    if not checks["expected_vertex_count_valid"]:
        blockers.append("TRIBE_EXPECTED_VERTEX_COUNT must be empty or a positive integer")
    if image_blocks and not checks["ffmpeg_available"]:
        blockers.append("ffmpeg is required to convert image blocks into constant-frame video")
    if checks["requires_s3_materialization"] and not checks["s3_bucket_present"]:
        blockers.append("S3_BUCKET_NAME is required for S3-backed audio/video blocks")
    if checks["requires_s3_materialization"] and not checks["aws_region_present"]:
        blockers.append("AWS_REGION is required for S3-backed audio/video blocks")
    if not checks["hf_token_present"]:
        warnings.append("HF_TOKEN is not set; official TRIBE text inference may need gated LLaMA access")
    if not checks["modal_package_available"]:
        warnings.append("modal package is not installed in this interpreter; deploy/call Modal from a Modal-enabled venv")

    return {
        "ready": not blockers,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


def classify_real_tribe_error(exc: BaseException) -> dict[str, Any] | None:
    message = str(exc)
    lowered_message = message.lower()
    if "gated repo" in lowered_message or "restricted and you are not in the authorized list" in lowered_message:
        repo_id = "unknown"
        for candidate in ("meta-llama/Llama-3.2-3B", "facebook/tribev2"):
            if candidate.lower() in lowered_message:
                repo_id = candidate
                break

        return {
            "type": "error",
            "code": "model_access_required",
            "message": (
                f"Model access is required for {repo_id}. Request/accept access on Hugging Face, "
                "then retry this run."
            ),
            "retryable": False,
            "details": {
                "provider": "huggingface",
                "repo_id": repo_id,
                "error_type": type(exc).__name__,
            },
        }
    if "403 client error" in lowered_message and "huggingface.co" in lowered_message:
        return {
            "type": "error",
            "code": "tribe_access_denied",
            "message": "Hugging Face denied access to a model required by TRIBE v2.",
            "retryable": False,
            "details": {
                "provider": "huggingface",
                "error_type": type(exc).__name__,
            },
        }
    return None


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


def convert_image_to_video(image_path: Path, destination: Path, *, duration_ms: int) -> Path:
    if duration_ms <= 0:
        raise ValueError("image block duration_ms must be positive")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to convert image blocks into constant-frame video")

    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-r",
            "2",
            "-an",
            str(destination),
        ],
        check=True,
    )
    return destination


def convert_audio_for_tribe(audio_path: Path, destination: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to convert browser-recorded audio")
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(audio_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(destination),
        ],
        check=True,
    )
    return destination


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
        if audio_path.suffix.lower() not in {".wav", ".mp3", ".flac", ".ogg"}:
            converted_path = working_dir / "inputs" / f"{_safe_file_stem(block, 'audio')}-tribe.wav"
            audio_path = convert_audio_for_tribe(audio_path, converted_path)
        return model.get_events_dataframe(audio_path=str(audio_path))
    if block_type == "image":
        image_path = _materialize_media_block(
            block,
            working_dir,
            extensions_by_mime=IMAGE_EXTENSIONS_BY_MIME,
            fallback_extension=".png",
        )
        video_path = working_dir / "inputs" / f"{_safe_file_stem(block, 'image')}.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        convert_image_to_video(image_path, video_path, duration_ms=int(block.get("duration_ms") or 0))
        return model.get_events_dataframe(video_path=str(video_path))
    if block_type == "video":
        video_path = _materialize_media_block(
            block,
            working_dir,
            extensions_by_mime=VIDEO_EXTENSIONS_BY_MIME,
            fallback_extension=".mp4",
        )
        return model.get_events_dataframe(video_path=str(video_path))

    raise ValueError("Real TRIBE inference supports image, text, audio, and video inputs.")


def _prediction_sample_rate_hz(model: Any, fallback: int) -> float:
    repetition_time = getattr(getattr(model, "data", None), "TR", None)
    if isinstance(repetition_time, (int, float)) and repetition_time > 0:
        return 1.0 / float(repetition_time)
    return float(fallback)


def _timing_metadata(block: dict[str, Any], events: Any, segments: Any) -> dict[str, Any]:
    word_timings: list[dict[str, Any]] = []
    if hasattr(events, "to_dict"):
        for row in events.to_dict(orient="records"):
            event_type = str(row.get("type") or "").lower()
            word = row.get("word") or row.get("text")
            start = row.get("start")
            duration = row.get("duration")
            if "word" not in event_type or not isinstance(word, str) or not isinstance(start, (int, float)):
                continue
            timing = {"word": word, "start_seconds": float(start)}
            if isinstance(duration, (int, float)):
                timing["end_seconds"] = float(start) + float(duration)
            word_timings.append(timing)

    return {
        "type": "stimulus_metadata",
        "block_id": str(block.get("id") or ""),
        "stimulus_type": str(block.get("type") or ""),
        "word_timings": word_timings,
        "segment_count": len(segments) if hasattr(segments, "__len__") else None,
        "hrf_offset_seconds": TRIBE_HRF_OFFSET_SECONDS,
    }


def run_real_tribe_stream(
    spec: dict[str, Any],
    *,
    model: Any | None = None,
    working_dir: Path | None = None,
) -> Generator[dict[str, Any], None, None]:
    blocks = _run_blocks(spec)
    job_id = str(spec.get("job_id") or "tribe-real")
    requested_sample_rate_hz = _sample_rate_hz(spec)

    yield {
        "type": "warming",
        "job_id": job_id,
        "reason": "tribe_model_loading",
        "estimated_seconds": 120,
    }

    model = model or load_tribe_model()
    sample_rate_hz = _prediction_sample_rate_hz(model, requested_sample_rate_hz)
    chunk_timesteps = _real_chunk_timesteps()
    expected_vertex_count = _expected_vertex_count()
    completed_timesteps = 0
    total_blocks = len(blocks)
    vertex_count = 0
    chunk_index = 0

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
        for block_index, block in enumerate(blocks):
            block_id = str(block.get("id") or f"block-{block_index}")
            events = _events_dataframe_for_block(model, block, working_dir)
            predictions, segments = model.predict(events=events)
            activations = validate_prediction_matrix(predictions, expected_vertex_count=expected_vertex_count)
            yield _timing_metadata(block, events, segments)

            vertex_count = int(activations.shape[1])
            for local_timestep_start, activation_chunk in iter_activation_chunks(
                activations=activations,
                chunk_timesteps=chunk_timesteps,
            ):
                yield activation_chunk_event(
                    job_id=job_id,
                    block_id=block_id,
                    chunk_index=chunk_index,
                    timestep_start=completed_timesteps + local_timestep_start,
                    sample_rate_hz=sample_rate_hz,
                    activations=activation_chunk,
                )
                chunk_index += 1

            completed_timesteps += int(activations.shape[0])
            yield {
                "type": "progress",
                "job_id": job_id,
                "completed_blocks": block_index + 1,
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
        readiness = check_real_tribe_config(spec)
        if not readiness["ready"]:
            yield {
                "type": "error",
                "job_id": str(spec.get("job_id") or "tribe-real"),
                "code": "tribe_not_ready",
                "message": "; ".join(readiness["blockers"]),
                "retryable": False,
                "readiness": readiness,
            }
            return
        try:
            yield from run_real_tribe_stream(spec)
        except Exception as exc:
            classified_error = classify_real_tribe_error(exc)
            if classified_error is None:
                raise
            classified_error["job_id"] = str(spec.get("job_id") or "tribe-real")
            yield classified_error
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
    fake_image = modal.Image.debian_slim(python_version="3.11").pip_install("numpy==2.2.1", "msgpack==1.1.0")
    real_image = (
        fake_image.apt_install("git", "ffmpeg")
        .pip_install(
            "boto3==1.35.90",
            OFFICIAL_TRIBE_SOURCE_URL,
        )
        .pip_install(f"exca=={COMPATIBLE_EXCA_VERSION}")
        .pip_install(f"transformers=={COMPATIBLE_TRANSFORMERS_VERSION}")
        .env(_real_tribe_env())
    )
    real_secrets = [modal.Secret.from_name(_modal_secret_name())]

    app = modal.App(APP_NAME)

    @app.function(image=fake_image, gpu="A10G", timeout=300)
    def run(spec: dict[str, Any]):
        os.environ["TRIBE_INFERENCE_MODE"] = "fake"
        yield from run_configured_stream(spec)

    @app.function(image=real_image, secrets=real_secrets, gpu="A10G", timeout=300)
    def run_real(spec: dict[str, Any]):
        yield from run_configured_stream(spec)

    @app.function(image=real_image, secrets=real_secrets, timeout=60)
    def check_real_runtime() -> dict[str, Any]:
        readiness = check_real_tribe_config({"blocks": []})
        result: dict[str, Any] = {
            "image_profile": "real",
            "readiness": readiness,
            "tribe_import_ok": False,
            "model_id": TRIBE_MODEL_ID,
            "model_loaded": False,
        }
        try:
            from tribev2 import TribeModel

            result["tribe_import_ok"] = True
            result["tribe_model_class"] = TribeModel.__name__
        except Exception as exc:  # pragma: no cover - only exercised inside Modal.
            result["tribe_import_error"] = f"{type(exc).__name__}: {exc}"

        try:
            import exca

            result["exca_version"] = getattr(exca, "__version__", "unknown")
        except Exception as exc:  # pragma: no cover - only exercised inside Modal.
            result["exca_import_error"] = f"{type(exc).__name__}: {exc}"

        return result

else:
    app = None


def main() -> None:
    parser = argparse.ArgumentParser(description="TRIBE inference Modal scaffold")
    parser.add_argument("--smoke", action="store_true", help="run the local fake stream contract smoke test")
    parser.add_argument(
        "--check-real-config",
        action="store_true",
        help="check real TRIBE configuration without loading the model or running inference",
    )
    args = parser.parse_args()

    if args.smoke:
        _print_smoke_events(run_fake_stream(_smoke_spec()))
        return
    if args.check_real_config:
        print(json.dumps(check_real_tribe_config(_smoke_spec()), indent=2, sort_keys=True))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
