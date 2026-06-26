from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.block import Block, BlockType
from app.models.experiment import Experiment, ExperimentStatus
from app.schemas.library import LibraryPublishRequest
from app.services.library import fork_library_entry, publish_experiment


class FakeResult:
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = values

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.values if self.values is not None else []


class FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.committed = False
        self.refreshed = []

    async def execute(self, statement):
        if not self.results:
            raise AssertionError(f"Unexpected query: {statement}")
        return self.results.pop(0)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        for item in self.added:
            if isinstance(item, Experiment) and item.id is None:
                item.id = uuid4()

    async def commit(self):
        self.committed = True

    async def refresh(self, item):
        self.refreshed.append(item)


def make_user():
    return SimpleNamespace(id=uuid4())


def make_experiment(owner_id, **overrides):
    data = {
        "id": uuid4(),
        "owner_id": owner_id,
        "name": "FFA pilot",
        "description": "Faces versus houses",
        "status": ExperimentStatus.draft,
        "is_public": False,
        "slug": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_entry(owner_id, experiment_id, **overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "experiment_id": experiment_id,
        "owner_id": owner_id,
        "slug": "ffa-face-localizer",
        "title": "FFA face localizer",
        "description": "Faces versus houses",
        "tags": ["vision"],
        "featured": False,
        "run_count": 0,
        "published_at": now,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_publish_experiment_requires_owned_experiment():
    session = FakeSession([FakeResult(None)])
    user = make_user()

    with pytest.raises(HTTPException) as exc:
        await publish_experiment(
            session,
            user,
            uuid4(),
            LibraryPublishRequest(title="FFA face localizer", slug="ffa-face-localizer"),
        )

    assert exc.value.status_code == 404
    assert session.committed is False


@pytest.mark.asyncio
async def test_publish_experiment_rejects_duplicate_slug():
    user = make_user()
    experiment = make_experiment(user.id)
    existing_entry = make_entry(uuid4(), uuid4(), slug="ffa-face-localizer")
    session = FakeSession(
        [
            FakeResult(experiment),
            FakeResult(1),
            FakeResult(existing_entry),
        ]
    )

    with pytest.raises(HTTPException) as exc:
        await publish_experiment(
            session,
            user,
            experiment.id,
            LibraryPublishRequest(title="FFA face localizer", slug="ffa-face-localizer"),
        )

    assert exc.value.status_code == 409
    assert "slug" in exc.value.detail.lower()
    assert session.committed is False


@pytest.mark.asyncio
async def test_fork_library_entry_copies_blocks_and_creates_private_draft():
    user = make_user()
    owner_id = uuid4()
    source_experiment_id = uuid4()
    entry = make_entry(owner_id, source_experiment_id, run_count=3)
    source = make_experiment(owner_id, id=source_experiment_id, is_public=True, slug="ffa-face-localizer")
    block = SimpleNamespace(
        id=uuid4(),
        type=BlockType.text,
        condition="faces",
        start_ms=0,
        duration_ms=1000,
        content_hash="sha256:abc",
        payload={"text": "face", "nested": {"copy": True}},
    )
    session = FakeSession(
        [
            FakeResult(entry),
            FakeResult(source),
            FakeResult(values=[block]),
        ]
    )

    response = await fork_library_entry(session, user, "ffa-face-localizer")

    fork = next(item for item in session.added if isinstance(item, Experiment))
    copied_block = next(item for item in session.added if isinstance(item, Block))
    assert response.experiment_id == fork.id
    assert fork.owner_id == user.id
    assert fork.name == "FFA pilot (Fork)"
    assert fork.status == ExperimentStatus.draft
    assert fork.is_public is False
    assert fork.slug is None
    assert copied_block.experiment_id == fork.id
    assert copied_block.type == BlockType.text
    assert copied_block.condition == "faces"
    assert copied_block.start_ms == 0
    assert copied_block.duration_ms == 1000
    assert copied_block.content_hash == "sha256:abc"
    assert copied_block.payload == block.payload
    assert copied_block.payload is not block.payload
    assert entry.run_count == 4
    assert session.committed is True
