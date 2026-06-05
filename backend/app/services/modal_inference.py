import base64
import asyncio
from collections.abc import AsyncIterator
from typing import Any

import msgpack

from app.schemas.sse import ChunkEnvelope


class ModalInferenceError(RuntimeError):
    pass


def encode_modal_chunk_event(event: dict[str, Any]) -> ChunkEnvelope:
    payload = dict(event)
    payload.pop("type", None)

    required_fields = {
        "job_id",
        "block_id",
        "chunk_index",
        "timestep_start",
        "timestep_count",
        "sample_rate_hz",
        "vertex_count",
        "dtype",
        "shape",
        "activations",
    }
    missing_fields = sorted(required_fields - payload.keys())
    if missing_fields:
        raise ModalInferenceError(f"Modal chunk event missing fields: {', '.join(missing_fields)}")

    if payload["dtype"] != "float32":
        raise ModalInferenceError(f"Unsupported activation dtype from Modal: {payload['dtype']}")
    if not isinstance(payload["activations"], bytes):
        raise ModalInferenceError("Modal chunk activations must be raw bytes")

    packed = msgpack.packb(payload, use_bin_type=True)
    return ChunkEnvelope(payload=base64.b64encode(packed).decode("ascii"))


async def stream_deployed_modal_events(
    *,
    app_name: str,
    function_name: str,
    spec: dict[str, Any],
    environment_name: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    try:
        import modal
    except ImportError as exc:
        raise ModalInferenceError(
            "Modal provider selected, but the modal package is not installed in the backend environment."
        ) from exc

    try:
        function = modal.Function.from_name(app_name, function_name, environment_name=environment_name)
        remote_gen_aio = getattr(function.remote_gen, "aio", None)
        if callable(remote_gen_aio):
            stream = remote_gen_aio(spec)
            async for event in stream:
                yield validate_modal_event(event)
            return

        stream = function.remote_gen(spec)
        if hasattr(stream, "__aiter__"):
            async for event in stream:
                yield validate_modal_event(event)
            return

        events = await asyncio.to_thread(list, stream)
        for event in events:
            yield validate_modal_event(event)
    except ModalInferenceError:
        raise
    except Exception as exc:
        raise ModalInferenceError(f"Modal inference call failed: {exc}") from exc


def validate_modal_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ModalInferenceError(f"Modal yielded unsupported event type: {type(event).__name__}")
    return event
