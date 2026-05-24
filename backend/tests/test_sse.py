import base64

import msgpack
import numpy as np
import pytest

from app.schemas.sse import CompleteEvent, ErrorEvent, ProgressEvent, QueuedEvent, WarmingEvent
from app.services.activation_events import encode_activation_chunk, fake_activation_chunk
from app.services.sse import encode_sse


def test_encode_sse_uses_single_line_json_data():
    event = encode_sse("queued", {"job_id": "job_1", "status": "queued"}, event_id=1)

    assert event == 'event: queued\nid: 1\ndata: {"job_id":"job_1","status":"queued"}\n\n'


def test_encode_sse_rejects_invalid_event_name():
    with pytest.raises(ValueError):
        encode_sse("bad\nevent", {"job_id": "job_1"})


def test_job_stream_event_payload_shapes():
    assert QueuedEvent(job_id="job_1").model_dump(mode="json") == {"job_id": "job_1", "status": "queued"}
    assert WarmingEvent(job_id="job_1", estimated_seconds=90).model_dump(mode="json") == {
        "job_id": "job_1",
        "reason": "modal_cold_start",
        "estimated_seconds": 90,
    }
    assert ProgressEvent(
        job_id="job_1",
        completed_blocks=1,
        total_blocks=2,
        completed_timesteps=4,
    ).model_dump(mode="json") == {
        "job_id": "job_1",
        "completed_blocks": 1,
        "total_blocks": 2,
        "completed_timesteps": 4,
    }
    assert CompleteEvent(job_id="job_1", timesteps=8, vertex_count=20484).model_dump(mode="json") == {
        "job_id": "job_1",
        "status": "complete",
        "result_s3_key": None,
        "timesteps": 8,
        "vertex_count": 20484,
    }
    assert ErrorEvent(
        job_id="job_1",
        code="validation_failed",
        message="bad run spec",
        retryable=False,
    ).model_dump(mode="json") == {
        "job_id": "job_1",
        "code": "validation_failed",
        "message": "bad run spec",
        "retryable": False,
        "last_timestep": None,
    }


def test_encode_activation_chunk_uses_base64_msgpack_float32_bytes():
    activations = np.array([[1.5, -2.0, 0.25]], dtype=np.float32)

    envelope = encode_activation_chunk(
        job_id="job_1",
        block_id="block_1",
        chunk_index=2,
        timestep_start=4,
        sample_rate_hz=2,
        activations=activations,
    )

    assert envelope.encoding == "base64-msgpack"
    decoded = msgpack.unpackb(base64.b64decode(envelope.payload), raw=False)
    assert decoded["job_id"] == "job_1"
    assert decoded["block_id"] == "block_1"
    assert decoded["chunk_index"] == 2
    assert decoded["timestep_start"] == 4
    assert decoded["timestep_count"] == 1
    assert decoded["sample_rate_hz"] == 2
    assert decoded["vertex_count"] == 3
    assert decoded["dtype"] == "float32"
    assert decoded["shape"] == [1, 3]
    assert np.frombuffer(decoded["activations"], dtype="<f4").tolist() == [1.5, -2.0, 0.25]


def test_fake_activation_chunk_is_deterministic():
    envelope = fake_activation_chunk(
        job_id="job_1",
        block_id="block_1",
        chunk_index=3,
        timestep_start=6,
        timestep_count=2,
        vertex_count=3,
    )

    decoded = msgpack.unpackb(base64.b64decode(envelope.payload), raw=False)
    assert decoded["shape"] == [2, 3]
    assert decoded["timestep_count"] == 2
    np.testing.assert_allclose(
        np.frombuffer(decoded["activations"], dtype="<f4").reshape(2, 3),
        np.array([[0.003, 1.003, 2.003], [3.003, 4.003, 5.003]], dtype=np.float32),
    )
