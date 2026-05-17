import pytest
from pydantic import ValidationError

from app.schemas.run import RunExperimentRequest


def test_run_request_accepts_image_block():
    request = RunExperimentRequest.model_validate(
        {
            "blocks": [
                {
                    "id": "block_1",
                    "type": "image",
                    "condition": "faces",
                    "start_ms": 0,
                    "duration_ms": 2000,
                    "content_hash": "sha256:abc123",
                    "s3_key": "uploads/block.png",
                    "mime_type": "image/png",
                }
            ]
        }
    )

    assert request.blocks[0].type == "image"


def test_run_request_rejects_overlapping_blocks():
    with pytest.raises(ValidationError):
        RunExperimentRequest.model_validate(
            {
                "blocks": [
                    {
                        "id": "block_1",
                        "type": "text",
                        "start_ms": 0,
                        "duration_ms": 2000,
                        "content_hash": "sha256:abc123",
                        "text": "hello",
                    },
                    {
                        "id": "block_2",
                        "type": "text",
                        "start_ms": 1000,
                        "duration_ms": 2000,
                        "content_hash": "sha256:def456",
                        "text": "world",
                    },
                ]
            }
        )

