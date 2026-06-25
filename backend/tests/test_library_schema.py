from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.library import LibraryPublishRequest, PublicLibraryExperimentBlock


def test_publish_request_accepts_public_metadata():
    request = LibraryPublishRequest(
        title="FFA Face House",
        description="Classic visual localizer",
        tags=["vision", "faces"],
        slug="ffa-face-house",
    )

    assert request.title == "FFA Face House"
    assert request.tags == ["vision", "faces"]


def test_publish_request_rejects_invalid_slug():
    with pytest.raises(ValidationError):
        LibraryPublishRequest(title="Bad slug", slug="Bad Slug!")


def test_public_block_schema_exposes_read_only_timeline_fields():
    block = PublicLibraryExperimentBlock(
        id=uuid4(),
        type="text",
        condition="language",
        start_ms=0,
        duration_ms=5000,
        payload={"text": "A short sentence."},
    )

    assert block.type == "text"
    assert block.payload["text"] == "A short sentence."
