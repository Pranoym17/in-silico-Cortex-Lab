import base64
from typing import Any

import msgpack
import numpy as np
from numpy.typing import NDArray

from app.schemas.sse import ChunkEnvelope


def _as_float32_matrix(activations: NDArray[np.float32]) -> NDArray[np.float32]:
    array = np.asarray(activations, dtype="<f4")
    if array.ndim == 1:
        array = array.reshape(1, array.shape[0])
    if array.ndim != 2:
        raise ValueError("activation chunks must be a 1D or 2D float32 array")
    return np.ascontiguousarray(array, dtype="<f4")


def encode_activation_chunk(
    *,
    job_id: str,
    block_id: str,
    chunk_index: int,
    timestep_start: int,
    sample_rate_hz: int,
    activations: NDArray[np.float32],
) -> ChunkEnvelope:
    matrix = _as_float32_matrix(activations)
    timestep_count, vertex_count = matrix.shape
    msgpack_payload: dict[str, Any] = {
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
    packed = msgpack.packb(msgpack_payload, use_bin_type=True)
    return ChunkEnvelope(payload=base64.b64encode(packed).decode("ascii"))


def fake_activation_chunk(
    *,
    job_id: str,
    block_id: str,
    chunk_index: int,
    timestep_start: int,
    timestep_count: int,
    vertex_count: int,
    sample_rate_hz: int = 2,
) -> ChunkEnvelope:
    if timestep_count <= 0:
        raise ValueError("timestep_count must be positive")
    if vertex_count <= 0:
        raise ValueError("vertex_count must be positive")

    values = np.arange(timestep_count * vertex_count, dtype=np.float32).reshape(timestep_count, vertex_count)
    values = values + np.float32(chunk_index / 1000)
    return encode_activation_chunk(
        job_id=job_id,
        block_id=block_id,
        chunk_index=chunk_index,
        timestep_start=timestep_start,
        sample_rate_hz=sample_rate_hz,
        activations=values,
    )
