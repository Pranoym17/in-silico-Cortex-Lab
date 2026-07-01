from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.block import BlockType
from app.schemas.block import BlockCreate, TemplateApplyRequest
from app.services.block_validation import TimelineBlock, validate_timeline
from app.services.blocks import apply_template, validate_block_content


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


def test_validate_block_content_accepts_owned_upload_key():
    owner = SimpleNamespace(id=uuid4())
    experiment_id = uuid4()
    block = SimpleNamespace(
        type=BlockType.image,
        duration_ms=1000,
        experiment_id=experiment_id,
        payload={"s3_key": f"uploads/{owner.id}/experiments/{experiment_id}/block/face.png"},
    )

    validate_block_content(block, owner)


def test_validate_block_content_accepts_trusted_stimulus_library_key():
    owner = SimpleNamespace(id=uuid4())
    block = SimpleNamespace(
        type=BlockType.image,
        duration_ms=2000,
        experiment_id=uuid4(),
        payload={"s3_key": "stimulus-library/v1/faces/face-001.png"},
    )

    validate_block_content(block, owner)


def test_validate_block_content_rejects_unowned_upload_key():
    owner = SimpleNamespace(id=uuid4())
    experiment_id = uuid4()
    block = SimpleNamespace(
        type=BlockType.audio,
        duration_ms=1000,
        experiment_id=experiment_id,
        payload={"s3_key": f"uploads/{uuid4()}/experiments/{experiment_id}/block/sound.wav"},
    )

    with pytest.raises(HTTPException) as exc:
        validate_block_content(block, owner)

    assert exc.value.status_code == 422
    assert exc.value.detail == "block media must reference an upload owned by this experiment"


def test_validate_block_content_rejects_audio_duration_mismatch():
    block = SimpleNamespace(
        type=BlockType.audio,
        duration_ms=10_000,
        experiment_id=uuid4(),
        payload={"duration_ms": 2_000},
    )

    with pytest.raises(HTTPException) as exc:
        validate_block_content(block)

    assert exc.value.status_code == 422
    assert exc.value.detail == "audio block duration must match the uploaded media duration"


@pytest.mark.asyncio
async def test_apply_template_rolls_back_replace_when_commit_fails(monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    experiment_id = uuid4()
    existing = SimpleNamespace(
        id=uuid4(),
        type=BlockType.text,
        condition="old",
        start_ms=0,
        duration_ms=1000,
        content_hash="sha256:old",
        payload={"text": "old"},
    )

    async def fake_get_owned_experiment(session, requested_owner, requested_experiment_id):
        return SimpleNamespace(status="draft")

    async def fake_list_blocks(session, requested_owner, requested_experiment_id):
        return [existing]

    class FailingSession:
        def __init__(self):
            self.deleted = []
            self.added = []
            self.rollbacks = 0

        async def delete(self, block):
            self.deleted.append(block)

        def add_all(self, blocks):
            self.added.extend(blocks)

        async def commit(self):
            raise RuntimeError("database unavailable")

        async def rollback(self):
            self.rollbacks += 1

    monkeypatch.setattr("app.services.blocks.get_owned_experiment", fake_get_owned_experiment)
    monkeypatch.setattr("app.services.blocks.list_blocks", fake_list_blocks)
    session = FailingSession()

    with pytest.raises(RuntimeError, match="database unavailable"):
        await apply_template(
            session,
            owner,
            experiment_id,
            TemplateApplyRequest(
                mode="replace",
                blocks=[
                    {
                        "type": "text",
                        "condition": "new",
                        "start_ms": 0,
                        "duration_ms": 1000,
                        "content_hash": "sha256:abcdef",
                        "payload": {"text": "new"},
                    }
                ],
            ),
        )

    assert session.deleted == [existing]
    assert len(session.added) == 1
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_apply_template_preserves_existing_block_identity(monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    experiment_id = uuid4()
    block_id = uuid4()
    existing = SimpleNamespace(
        id=block_id,
        type=BlockType.text,
        condition="old",
        start_ms=0,
        duration_ms=1000,
        content_hash=None,
        payload={"text": "old"},
    )

    async def fake_get_owned_experiment(session, requested_owner, requested_experiment_id):
        return SimpleNamespace(status="draft")

    async def fake_list_blocks(session, requested_owner, requested_experiment_id):
        return [existing]

    class Session:
        def __init__(self):
            self.deleted = []
            self.added = []
            self.commits = 0

        async def delete(self, block):
            self.deleted.append(block)

        def add_all(self, blocks):
            self.added.extend(blocks)

        async def commit(self):
            self.commits += 1

        async def refresh(self, block):
            return None

        async def rollback(self):
            raise AssertionError("rollback should not be called")

    monkeypatch.setattr("app.services.blocks.get_owned_experiment", fake_get_owned_experiment)
    monkeypatch.setattr("app.services.blocks.list_blocks", fake_list_blocks)
    session = Session()

    result = await apply_template(
        session,
        owner,
        experiment_id,
        TemplateApplyRequest(
            mode="replace",
            blocks=[
                {
                    "id": block_id,
                    "type": "text",
                    "condition": "new",
                    "start_ms": 500,
                    "duration_ms": 1500,
                    "payload": {"text": "updated"},
                }
            ],
        ),
    )

    assert result == [existing]
    assert existing.id == block_id
    assert existing.condition == "new"
    assert existing.payload == {"text": "updated"}
    assert session.deleted == []
    assert session.added == []
    assert session.commits == 1
