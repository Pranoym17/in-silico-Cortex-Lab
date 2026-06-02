import base64

import msgpack
import pytest

from app.services.modal_inference import ModalInferenceError, encode_modal_chunk_event


def valid_chunk_event():
    return {
        "type": "chunk",
        "job_id": "job-1",
        "block_id": "block-1",
        "chunk_index": 0,
        "timestep_start": 0,
        "timestep_count": 1,
        "sample_rate_hz": 2,
        "vertex_count": 2,
        "dtype": "float32",
        "shape": [1, 2],
        "activations": b"\x00\x00\x00\x00\x00\x00\x80?",
    }


def test_encode_modal_chunk_event_wraps_base64_msgpack_payload():
    envelope = encode_modal_chunk_event(valid_chunk_event())

    unpacked = msgpack.unpackb(base64.b64decode(envelope.payload), raw=False)

    assert envelope.encoding == "base64-msgpack"
    assert unpacked["job_id"] == "job-1"
    assert unpacked["block_id"] == "block-1"
    assert unpacked["shape"] == [1, 2]
    assert unpacked["activations"] == b"\x00\x00\x00\x00\x00\x00\x80?"
    assert "type" not in unpacked


def test_encode_modal_chunk_event_rejects_missing_fields():
    event = valid_chunk_event()
    event.pop("activations")

    with pytest.raises(ModalInferenceError, match="missing fields: activations"):
        encode_modal_chunk_event(event)


def test_encode_modal_chunk_event_rejects_non_binary_activations():
    event = valid_chunk_event()
    event["activations"] = "not-bytes"

    with pytest.raises(ModalInferenceError, match="raw bytes"):
        encode_modal_chunk_event(event)
