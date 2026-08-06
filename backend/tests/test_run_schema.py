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


def test_run_request_rejects_audio_duration_mismatch():
    with pytest.raises(ValidationError, match="must match"):
        RunExperimentRequest.model_validate(
            {
                "blocks": [
                    {
                        "id": "audio-1",
                        "type": "audio",
                        "start_ms": 0,
                        "duration_ms": 10_000,
                        "source_duration_ms": 2_000,
                        "content_hash": "sha256:abc123",
                        "s3_key": "uploads/audio.wav",
                        "mime_type": "audio/wav",
                        "channels": 1,
                        "sample_rate_hz": 16_000,
                    }
                ]
            }
        )


def test_run_request_accepts_trimmed_video_range():
    request = RunExperimentRequest.model_validate(
        {
            "blocks": [
                {
                    "id": "video-1",
                    "type": "video",
                    "start_ms": 0,
                    "duration_ms": 4_000,
                    "source_duration_ms": 10_000,
                    "trim_start_ms": 5_000,
                    "content_hash": "sha256:abc123",
                    "s3_key": "uploads/video.mp4",
                    "mime_type": "video/mp4",
                }
            ]
        }
    )

    assert request.blocks[0].trim_start_ms == 5_000


def test_run_request_rejects_video_trim_outside_source_duration():
    with pytest.raises(ValidationError, match="trim range"):
        RunExperimentRequest.model_validate(
            {
                "blocks": [
                    {
                        "id": "video-1",
                        "type": "video",
                        "start_ms": 0,
                        "duration_ms": 6_000,
                        "source_duration_ms": 10_000,
                        "trim_start_ms": 5_000,
                        "content_hash": "sha256:abc123",
                        "s3_key": "uploads/video.mp4",
                        "mime_type": "video/mp4",
                    }
                ]
            }
        )

