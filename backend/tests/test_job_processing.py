from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.job import JobStatus
from app.services.job_processing import JobProcessingError, process_fake_inference_job
from app.tasks.inference_task import _run_inference


def valid_run_spec():
    return {
        "blocks": [
            {
                "id": str(uuid4()),
                "type": "text",
                "condition": "language",
                "start_ms": 0,
                "duration_ms": 1000,
                "content_hash": "sha256:abc123",
                "text": "face",
            }
        ],
        "settings": {
            "hrf_offset_ms": 5000,
            "target_sample_rate_hz": 2,
            "surface": "fsaverage5",
            "atlas": "desikan-killiany",
        },
    }


def make_job(**overrides):
    data = {
        "id": uuid4(),
        "status": JobStatus.queued,
        "run_spec": valid_run_spec(),
        "error_code": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeScalarResult:
    def __init__(self, job):
        self.job = job

    def scalar_one_or_none(self):
        return self.job


class FakeSession:
    def __init__(self, job):
        self.job = job
        self.commits = 0
        self.refreshed = []

    async def execute(self, query):
        return FakeScalarResult(self.job)

    async def commit(self):
        self.commits += 1

    async def refresh(self, job):
        self.refreshed.append(job)


@pytest.mark.asyncio
async def test_process_fake_inference_job_completes_valid_job():
    job = make_job()
    session = FakeSession(job)

    processed = await process_fake_inference_job(session, job.id)

    assert processed is job
    assert job.status == JobStatus.complete
    assert job.error_code is None
    assert job.error_message is None
    assert isinstance(job.started_at, datetime)
    assert isinstance(job.completed_at, datetime)
    assert job.started_at.tzinfo == UTC
    assert job.completed_at.tzinfo == UTC
    assert session.commits == 2
    assert session.refreshed == [job, job]


@pytest.mark.asyncio
async def test_process_fake_inference_job_marks_invalid_snapshot_failed():
    job = make_job(run_spec={"blocks": [], "settings": {}})
    session = FakeSession(job)

    processed = await process_fake_inference_job(session, job.id)

    assert processed is job
    assert job.status == JobStatus.failed
    assert job.error_code == "validation_failed"
    assert "List should have at least 1 item" in job.error_message
    assert isinstance(job.completed_at, datetime)
    assert session.commits == 1
    assert session.refreshed == [job]


@pytest.mark.asyncio
async def test_process_fake_inference_job_is_idempotent_for_terminal_status():
    job = make_job(status=JobStatus.complete, completed_at=datetime.now(UTC))
    session = FakeSession(job)

    processed = await process_fake_inference_job(session, job.id)

    assert processed is job
    assert job.status == JobStatus.complete
    assert session.commits == 0
    assert session.refreshed == []


@pytest.mark.asyncio
async def test_process_fake_inference_job_rejects_missing_job():
    session = FakeSession(None)

    with pytest.raises(JobProcessingError) as exc:
        await process_fake_inference_job(session, uuid4())

    assert "was not found" in str(exc.value)


@pytest.mark.asyncio
async def test_run_inference_rejects_invalid_job_id():
    with pytest.raises(JobProcessingError) as exc:
        await _run_inference("not-a-uuid")

    assert "Invalid job id" in str(exc.value)
