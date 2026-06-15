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
    timeout_seconds: int | None = None,
    max_attempts: int = 1,
) -> AsyncIterator[dict[str, Any]]:
    try:
        import modal
    except ImportError as exc:
        raise ModalInferenceError(
            "Modal provider selected, but the modal package is not installed in the backend environment."
        ) from exc

    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        yielded_chunk = False
        try:
            function = modal.Function.from_name(app_name, function_name, environment_name=environment_name)
            async for event in _stream_modal_function_events(function, spec, timeout_seconds=timeout_seconds):
                if event.get("type") == "chunk":
                    yielded_chunk = True
                yield event
            return
        except Exception as exc:
            if attempt < attempts and not yielded_chunk and is_retryable_modal_exception(exc):
                continue
            if isinstance(exc, ModalInferenceError):
                raise
            raise ModalInferenceError(f"Modal inference call failed: {exc}") from exc


def validate_modal_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ModalInferenceError(f"Modal yielded unsupported event type: {type(event).__name__}")
    return event


async def _stream_modal_function_events(function: Any, spec: dict[str, Any], *, timeout_seconds: int | None):
    remote_gen_aio = getattr(function.remote_gen, "aio", None)
    if callable(remote_gen_aio):
        async for event in _iterate_async_stream(remote_gen_aio(spec), timeout_seconds=timeout_seconds):
            yield validate_modal_event(event)
        return

    stream = function.remote_gen(spec)
    if hasattr(stream, "__aiter__"):
        async for event in _iterate_async_stream(stream, timeout_seconds=timeout_seconds):
            yield validate_modal_event(event)
        return

    try:
        if timeout_seconds is None:
            events = await asyncio.to_thread(list, stream)
        else:
            events = await asyncio.wait_for(asyncio.to_thread(list, stream), timeout=timeout_seconds)
    except TimeoutError as exc:
        raise ModalInferenceError(f"Modal inference timed out after {timeout_seconds} seconds.") from exc
    for event in events:
        yield validate_modal_event(event)


async def _iterate_async_stream(stream: Any, *, timeout_seconds: int | None):
    iterator = stream.__aiter__()
    while True:
        try:
            if timeout_seconds is None:
                event = await iterator.__anext__()
            else:
                event = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_seconds)
        except StopAsyncIteration:
            return
        except TimeoutError as exc:
            raise ModalInferenceError(f"Modal inference timed out after {timeout_seconds} seconds.") from exc
        yield event


def is_retryable_modal_exception(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("timeout", "timed out", "temporarily unavailable", "connection", "503", "502", "504"))
