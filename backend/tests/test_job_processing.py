import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import msgpack
import pytest

from app.models.job import JobStatus
from app.services.job_processing import FAKE_VERTEX_COUNT
from app.services.job_processing import JobProcessingError, process_fake_inference_job, process_modal_inference_job
from app.services.sse_broker import JobEventBroker
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


class FakeBroker:
    def __init__(self):
        self.events = []

    async def publish(self, job_id, event, data):
        self.events.append((job_id, event, data))


@pytest.mark.asyncio
async def test_process_fake_inference_job_completes_valid_job():
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    processed = await process_fake_inference_job(session, job.id, broker)

    assert processed is job
    assert job.status == JobStatus.complete
    assert job.error_code is None
    assert job.error_message is None
    assert isinstance(job.started_at, datetime)
    assert isinstance(job.completed_at, datetime)
    assert job.started_at.tzinfo == UTC
    assert job.completed_at.tzinfo == UTC
    assert session.commits == 3
    assert session.refreshed == [job, job, job]
    assert [event for _, event, _ in broker.events] == [
        "queued",
        "warming",
        "progress",
        "chunk",
        "progress",
        "complete",
    ]
    assert broker.events[0][2] == {"job_id": str(job.id), "status": "queued"}
    assert broker.events[2][2] == {
        "job_id": str(job.id),
        "completed_blocks": 0,
        "total_blocks": 1,
        "completed_timesteps": 0,
    }
    assert broker.events[4][2] == {
        "job_id": str(job.id),
        "completed_blocks": 1,
        "total_blocks": 1,
        "completed_timesteps": 1,
    }
    assert broker.events[5][2] == {
        "job_id": str(job.id),
        "status": "complete",
        "result_s3_key": None,
        "timesteps": 1,
        "vertex_count": FAKE_VERTEX_COUNT,
    }

    chunk_payload = msgpack.unpackb(base64.b64decode(broker.events[3][2]["payload"]), raw=False)
    assert broker.events[3][2]["encoding"] == "base64-msgpack"
    assert chunk_payload["job_id"] == str(job.id)
    assert chunk_payload["block_id"] == job.run_spec["blocks"][0]["id"]
    assert chunk_payload["vertex_count"] == FAKE_VERTEX_COUNT


@pytest.mark.asyncio
async def test_process_fake_inference_job_publishes_replayable_broker_events():
    job = make_job()
    session = FakeSession(job)
    broker = JobEventBroker()

    await process_fake_inference_job(session, job.id, broker)

    replayed = await broker.replay(job.id)

    assert [event.event for event in replayed] == [
        "queued",
        "warming",
        "progress",
        "chunk",
        "progress",
        "complete",
    ]
    assert [event.id for event in replayed] == [1, 2, 3, 4, 5, 6]
    assert replayed[-1].data["status"] == "complete"


@pytest.mark.asyncio
async def test_process_fake_inference_job_marks_invalid_snapshot_failed():
    job = make_job(run_spec={"blocks": [], "settings": {}})
    session = FakeSession(job)
    broker = FakeBroker()

    processed = await process_fake_inference_job(session, job.id, broker)

    assert processed is job
    assert job.status == JobStatus.failed
    assert job.error_code == "validation_failed"
    assert "List should have at least 1 item" in job.error_message
    assert isinstance(job.completed_at, datetime)
    assert session.commits == 1
    assert session.refreshed == [job]
    assert [event for _, event, _ in broker.events] == ["queued", "error"]
    assert broker.events[1][2] == {
        "job_id": str(job.id),
        "code": "validation_failed",
        "message": "Run specification failed validation.",
        "retryable": False,
        "last_timestep": None,
    }


@pytest.mark.asyncio
async def test_process_fake_inference_job_is_idempotent_for_terminal_status():
    job = make_job(status=JobStatus.complete, completed_at=datetime.now(UTC))
    session = FakeSession(job)
    broker = FakeBroker()

    processed = await process_fake_inference_job(session, job.id, broker)

    assert processed is job
    assert job.status == JobStatus.complete
    assert session.commits == 0
    assert session.refreshed == []
    assert broker.events == []


@pytest.mark.asyncio
async def test_process_fake_inference_job_rejects_missing_job():
    session = FakeSession(None)
    broker = FakeBroker()

    with pytest.raises(JobProcessingError) as exc:
        await process_fake_inference_job(session, uuid4(), broker)

    assert "was not found" in str(exc.value)
    assert broker.events == []


@pytest.mark.asyncio
async def test_process_modal_inference_job_publishes_modal_stream(monkeypatch):
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    async def fake_stream_deployed_modal_events(**kwargs):
        assert kwargs["app_name"] == "cortex-lab-tribe-inference"
        assert kwargs["function_name"] == "run"
        assert kwargs["environment_name"] is None
        assert kwargs["spec"]["job_id"] == str(job.id)
        block_id = kwargs["spec"]["blocks"][0]["id"]
        yield {"type": "warming", "job_id": str(job.id), "reason": "modal_fake_provider", "estimated_seconds": 1}
        yield {
            "type": "progress",
            "job_id": str(job.id),
            "completed_blocks": 0,
            "total_blocks": 1,
            "completed_timesteps": 0,
        }
        yield {
            "type": "chunk",
            "job_id": str(job.id),
            "block_id": block_id,
            "chunk_index": 0,
            "timestep_start": 0,
            "timestep_count": 1,
            "sample_rate_hz": 2,
            "vertex_count": 2,
            "dtype": "float32",
            "shape": [1, 2],
            "activations": b"\x00\x00\x00\x00\x00\x00\x80?",
        }
        yield {
            "type": "complete",
            "job_id": str(job.id),
            "status": "complete",
            "timesteps": 1,
            "vertex_count": 2,
        }

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)

    processed = await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run",
    )

    assert processed is job
    assert job.status == JobStatus.complete
    assert [event for _, event, _ in broker.events] == ["queued", "warming", "progress", "chunk", "complete"]
    chunk_payload = msgpack.unpackb(base64.b64decode(broker.events[3][2]["payload"]), raw=False)
    assert broker.events[3][2]["encoding"] == "base64-msgpack"
    assert chunk_payload["job_id"] == str(job.id)
    assert chunk_payload["vertex_count"] == 2
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "status": "complete",
        "result_s3_key": None,
        "timesteps": 1,
        "vertex_count": 2,
    }


@pytest.mark.asyncio
async def test_process_modal_inference_job_marks_partial_failure(monkeypatch):
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    async def fake_stream_deployed_modal_events(**kwargs):
        block_id = kwargs["spec"]["blocks"][0]["id"]
        yield {
            "type": "chunk",
            "job_id": str(job.id),
            "block_id": block_id,
            "chunk_index": 0,
            "timestep_start": 0,
            "timestep_count": 1,
            "sample_rate_hz": 2,
            "vertex_count": 2,
            "dtype": "float32",
            "shape": [1, 2],
            "activations": b"\x00\x00\x00\x00\x00\x00\x80?",
        }
        raise RuntimeError("modal crashed")

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)

    processed = await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run",
    )

    assert processed is job
    assert job.status == JobStatus.failed
    assert job.error_code == "partial_failure"
    assert "modal crashed" in job.error_message
    assert [event for _, event, _ in broker.events] == ["queued", "chunk", "error"]
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "code": "partial_failure",
        "message": "Inference failed after streaming partial results.",
        "retryable": True,
        "last_timestep": 0,
    }


@pytest.mark.asyncio
async def test_run_inference_rejects_invalid_job_id():
    with pytest.raises(JobProcessingError) as exc:
        await _run_inference("not-a-uuid")

    assert "Invalid job id" in str(exc.value)
