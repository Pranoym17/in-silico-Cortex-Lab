from __future__ import annotations

import argparse
import json
from collections.abc import Generator, Iterable
from typing import Any

import numpy as np

try:
    import modal
except ImportError:  # Modal is optional for local contract tests.
    modal = None


APP_NAME = "cortex-lab-tribe-inference"
FUNCTION_NAME = "run"
FAKE_VERTEX_COUNT = 16
FAKE_TIMESTEPS_PER_BLOCK = 1
DEFAULT_SAMPLE_RATE_HZ = 2


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
        yield from run_fake_stream(spec)

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
