from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.block import BlockType
from app.models.experiment import ExperimentStatus
from app.models.job import JobStatus
from app.services.jobs import block_to_run_spec, cancel_owned_job, create_job_from_experiment


def make_block(block_type: BlockType, **overrides):
    data = {
        "id": uuid4(),
        "type": block_type,
        "condition": "faces",
        "start_ms": 0,
        "duration_ms": 1000,
        "content_hash": "sha256:abc123",
        "payload": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_block_to_run_spec_maps_image_payload():
    block = make_block(
        BlockType.image,
        payload={
            "s3_key": "uploads/user/stimulus.webp",
            "mime_type": "image/webp",
            "display": {"mode": "full_bleed"},
        },
    )

    spec = block_to_run_spec(block)

    assert spec == {
        "id": str(block.id),
        "type": "image",
        "condition": "faces",
        "start_ms": 0,
        "duration_ms": 1000,
        "content_hash": "sha256:abc123",
        "s3_key": "uploads/user/stimulus.webp",
        "mime_type": "image/webp",
        "display": {"mode": "full_bleed"},
    }


def test_block_to_run_spec_requires_content_hash():
    block = make_block(BlockType.text, content_hash=None, payload={"text": "hello"})

    with pytest.raises(HTTPException) as exc:
        block_to_run_spec(block)

    assert exc.value.status_code == 422
    assert exc.value.detail == "all blocks require content_hash"


def test_block_to_run_spec_requires_type_specific_payload():
    block = make_block(BlockType.audio, payload={"mime_type": "audio/wav"})

    with pytest.raises(HTTPException) as exc:
        block_to_run_spec(block)

    assert exc.value.status_code == 422
    assert exc.value.detail == "audio blocks require s3_key"


@pytest.mark.asyncio
async def test_create_job_from_experiment_persists_snapshot(monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    experiment_id = uuid4()
    added = []
    committed = False
    refreshed = []

    async def fake_get_owned_experiment(session, requested_owner, requested_experiment_id):
        assert requested_owner is owner
        assert requested_experiment_id == experiment_id
        return SimpleNamespace(status=ExperimentStatus.draft)

    async def fake_list_blocks(session, requested_owner, requested_experiment_id):
        assert requested_owner is owner
        assert requested_experiment_id == experiment_id
        return [
            make_block(
                BlockType.text,
                payload={"text": "face"},
                duration_ms=1000,
            )
        ]

    class FakeSession:
        def add(self, job):
            added.append(job)

        async def commit(self):
            nonlocal committed
            committed = True

        async def refresh(self, job):
            refreshed.append(job)

    monkeypatch.setattr("app.services.jobs.get_owned_experiment", fake_get_owned_experiment)
    monkeypatch.setattr("app.services.jobs.list_blocks", fake_list_blocks)

    job = await create_job_from_experiment(FakeSession(), owner, experiment_id)

    assert added == [job]
    assert committed is True
    assert refreshed == [job]
    assert job.experiment_id == experiment_id
    assert job.owner_id == owner.id
    assert job.status == JobStatus.queued
    assert job.run_spec["blocks"][0]["type"] == "text"
    assert job.run_spec["blocks"][0]["text"] == "face"
    assert job.run_spec["settings"]["surface"] == "fsaverage5"


@pytest.mark.asyncio
async def test_create_job_from_experiment_rejects_archived_experiment(monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    experiment_id = uuid4()

    async def fake_get_owned_experiment(session, requested_owner, requested_experiment_id):
        assert requested_owner is owner
        assert requested_experiment_id == experiment_id
        return SimpleNamespace(status=ExperimentStatus.archived)

    async def fake_list_blocks(session, requested_owner, requested_experiment_id):
        raise AssertionError("archived experiments should fail before loading blocks")

    monkeypatch.setattr("app.services.jobs.get_owned_experiment", fake_get_owned_experiment)
    monkeypatch.setattr("app.services.jobs.list_blocks", fake_list_blocks)

    with pytest.raises(HTTPException) as exc:
        await create_job_from_experiment(SimpleNamespace(), owner, experiment_id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Archived experiments cannot be run"


@pytest.mark.asyncio
async def test_cancel_owned_job_marks_job_cancelled_and_publishes_sse(monkeypatch):
    owner = SimpleNamespace(id=uuid4())
    job = SimpleNamespace(
        id=uuid4(),
        owner_id=owner.id,
        status=JobStatus.running,
        error_code=None,
        error_message=None,
        completed_at=None,
    )
    published = []

    async def fake_get_owned_job(session, requested_owner, requested_job_id):
        assert requested_owner is owner
        assert requested_job_id == job.id
        return job

    class FakeSession:
        async def commit(self):
            return None

        async def refresh(self, value):
            return None

    class FakeBroker:
        async def publish(self, job_id, event, data):
            published.append((job_id, event, data))

    monkeypatch.setattr("app.services.jobs.get_owned_job", fake_get_owned_job)

    cancelled = await cancel_owned_job(FakeSession(), owner, job.id, FakeBroker())

    assert cancelled is job
    assert job.status == JobStatus.cancelled
    assert job.error_code == "cancelled"
    assert job.error_message == "Job was cancelled by the user."
    assert published == [
        (
            job.id,
            "error",
            {
                "job_id": str(job.id),
                "code": "cancelled",
                "message": "Job was cancelled by the user.",
                "retryable": False,
                "last_timestep": None,
            },
        )
    ]
