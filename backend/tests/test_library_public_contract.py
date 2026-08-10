from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services.library import public_author_response, public_block_payload, public_entry_response


def test_public_entry_hides_internal_identifiers():
    now = datetime.now(UTC)
    entry = SimpleNamespace(
        id=uuid4(), experiment_id=uuid4(), owner_id=uuid4(), slug="safe-entry", title="Safe", description=None,
        tags=[], featured=False, run_count=0, published_at=now, created_at=now, updated_at=now,
    )
    response = public_entry_response(entry)
    payload = response.model_dump()
    assert "owner_id" not in payload
    assert "experiment_id" not in payload


def test_public_blocks_never_expose_private_storage_references():
    payload = {"s3_key": "uploads/user/private.wav", "object_key": "secret", "transcript": "hello", "title": "Speech"}
    assert public_block_payload("audio", payload) == {"title": "Speech", "transcript": "hello"}
    assert public_block_payload("image", {"s3_key": "private", "display_mode": "full_bleed"}) == {"display_mode": "full_bleed"}


def test_public_author_uses_safe_fallback_name():
    assert public_author_response(SimpleNamespace(display_name="", avatar_url=None)).display_name == "Cortex Lab researcher"
