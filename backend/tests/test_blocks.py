from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.block import BlockType
from app.schemas.block import BlockCreate
from app.services.block_validation import TimelineBlock, validate_timeline


def test_block_create_accepts_text_payload():
    block = BlockCreate(
        type="text",
        condition="language",
        start_ms=0,
        duration_ms=5000,
        payload={"text": "The dog chased the ball.", "voice": "kokoro_default"},
    )

    assert block.type == BlockType.text
    assert block.payload["voice"] == "kokoro_default"


def test_block_create_rejects_invalid_image_duration():
    with pytest.raises(ValidationError):
        BlockCreate(
            type="image",
            start_ms=0,
            duration_ms=100,
            payload={"source": "library", "library_id": "face_001"},
        )


def test_block_create_rejects_long_text():
    with pytest.raises(ValidationError):
        BlockCreate(
            type="text",
            start_ms=0,
            duration_ms=5000,
            payload={"text": "word " * 1025},
        )


def test_validate_timeline_rejects_overlap():
    with pytest.raises(HTTPException) as exc:
        validate_timeline(
            [
                TimelineBlock(id=uuid4(), type=BlockType.image, start_ms=0, duration_ms=2000),
                TimelineBlock(id=uuid4(), type=BlockType.text, start_ms=1000, duration_ms=2000),
            ]
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "stimulus blocks cannot overlap"


def test_validate_timeline_rejects_duration_cap():
    with pytest.raises(HTTPException) as exc:
        validate_timeline(
            [
                TimelineBlock(id=uuid4(), type=BlockType.audio, start_ms=299000, duration_ms=2000),
            ]
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "experiment duration cannot exceed 300000ms"

