import base64
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import msgpack
import pytest

from app.models.job import JobStatus
from app.services.result_cache import CachedResult
from app.services.result_storage import ResultStorageError
from app.services.job_processing import FAKE_VERTEX_COUNT
from app.services.job_processing import (
    JobProcessingError,
    complete_job_from_cached_result,
    process_fake_inference_job,
    process_modal_inference_job,
)
from app.services.job_processing import user_facing_inference_failure
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
        "experiment_id": uuid4(),
        "owner_id": uuid4(),
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
        self.rollbacks = 0
        self.refreshed = []
        self.added = []

    async def execute(self, query):
        return FakeScalarResult(self.job)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, job):
        self.refreshed.append(job)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


@pytest.fixture(autouse=True)
def fake_result_storage(monkeypatch):
    class FakeS3Client:
        def put_object(self, **kwargs):
            return None

    monkeypatch.setattr("app.services.result_storage._s3_client", lambda: FakeS3Client())
    monkeypatch.setenv("S3_BUCKET_NAME", "test-results")
    monkeypatch.setenv("RESULTS_S3_PREFIX", "results")
    monkeypatch.setattr("app.services.job_processing.set_cached_result", lambda content_hash, result, context=None: None)
    yield


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
    assert session.refreshed.count(job) >= 3
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
        "result_s3_key": f"results/{job.id}/activations.npz",
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
        "result_s3_key": f"results/{job.id}/activations.npz",
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
async def test_process_modal_inference_job_publishes_sanitized_internal_error(monkeypatch):
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    async def fake_stream_deployed_modal_events(**kwargs):
        if False:
            yield
        raise RuntimeError("Modal inference call failed: Function not found: cortex-lab-tribe-inference.run_real")

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)

    processed = await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run_real",
    )

    assert processed is job
    assert job.status == JobStatus.failed
    assert job.error_code == "internal_error"
    assert "Function not found" in job.error_message
    assert [event for _, event, _ in broker.events] == ["queued", "error"]
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "code": "internal_error",
        "message": (
            "Modal inference endpoint was not found. Check MODAL_APP_NAME and MODAL_FUNCTION_NAME. "
            "Details: Function not found: cortex-lab-tribe-inference.run_real"
        ),
        "retryable": True,
        "last_timestep": None,
    }


def test_user_facing_inference_failure_preserves_modal_install_guidance():
    message = user_facing_inference_failure(
        RuntimeError("Modal provider selected, but the modal package is not installed in the backend environment."),
        chunk_seen=False,
    )

    assert message == "Modal provider selected, but the modal package is not installed in the backend environment."


@pytest.mark.asyncio
async def test_process_modal_inference_job_preserves_model_access_errors(monkeypatch):
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    async def fake_stream_deployed_modal_events(**kwargs):
        yield {
            "type": "error",
            "job_id": str(job.id),
            "code": "model_access_required",
            "message": "Model access is required for meta-llama/Llama-3.2-3B.",
            "retryable": False,
            "details": {
                "provider": "huggingface",
                "repo_id": "meta-llama/Llama-3.2-3B",
            },
        }

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)

    processed = await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run_real",
    )

    assert processed is job
    assert job.status == JobStatus.failed
    assert job.error_code == "model_access_required"
    assert job.error_message == "Model access is required for meta-llama/Llama-3.2-3B."
    assert [event for _, event, _ in broker.events] == ["queued", "error"]
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "code": "model_access_required",
        "message": "Model access is required for meta-llama/Llama-3.2-3B.",
        "retryable": False,
        "last_timestep": None,
    }


@pytest.mark.asyncio
async def test_process_modal_inference_job_normalizes_unknown_modal_error_codes(monkeypatch):
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    async def fake_stream_deployed_modal_events(**kwargs):
        yield {
            "type": "error",
            "job_id": str(job.id),
            "code": "modal_error",
            "message": "Modal inference failed.",
            "retryable": True,
        }

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)

    await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run_real",
    )

    assert job.error_code == "internal_error"
    assert broker.events[-1][2]["code"] == "internal_error"


@pytest.mark.asyncio
async def test_process_modal_inference_job_maps_oom_errors(monkeypatch):
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()

    async def fake_stream_deployed_modal_events(**kwargs):
        if False:
            yield
        raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)

    await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run_real",
    )

    assert job.error_code == "modal_oom"
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "code": "modal_oom",
        "message": "Modal ran out of memory while running inference.",
        "retryable": False,
        "last_timestep": None,
    }


@pytest.mark.asyncio
async def test_process_modal_inference_job_maps_result_storage_failure(monkeypatch):
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
        yield {"type": "complete", "job_id": str(job.id), "status": "complete", "timesteps": 1, "vertex_count": 2}

    async def fake_store_job_result(*args, **kwargs):
        raise ResultStorageError("S3 put_object failed")

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)
    monkeypatch.setattr("app.services.job_processing.store_job_result", fake_store_job_result)

    await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run_real",
    )

    assert job.error_code == "result_storage_failed"
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "code": "result_storage_failed",
        "message": "Inference finished, but the result artifact could not be saved.",
        "retryable": True,
        "last_timestep": 0,
    }


@pytest.mark.asyncio
async def test_process_modal_inference_job_rolls_back_result_if_cancelled_before_complete(monkeypatch):
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
        yield {"type": "complete", "job_id": str(job.id), "status": "complete", "timesteps": 1, "vertex_count": 2}

    async def fake_store_job_result(*args, **kwargs):
        job.status = JobStatus.cancelled
        return SimpleNamespace(
            s3_key="results/job/activations.npz",
            model_version=None,
        )

    monkeypatch.setattr("app.services.job_processing.stream_deployed_modal_events", fake_stream_deployed_modal_events)
    monkeypatch.setattr("app.services.job_processing.store_job_result", fake_store_job_result)

    processed = await process_modal_inference_job(
        session,
        job.id,
        broker,
        app_name="cortex-lab-tribe-inference",
        function_name="run_real",
    )

    assert processed.status == JobStatus.cancelled
    assert session.rollbacks == 1
    assert "complete" not in [event for _, event, _ in broker.events]


@pytest.mark.asyncio
async def test_complete_job_from_cached_result_marks_job_complete():
    job = make_job()
    session = FakeSession(job)
    broker = FakeBroker()
    cached = CachedResult(
        s3_key="results/cached/activations.npz",
        shape=[4, 20484],
        vertex_count=20484,
        timestep_count=4,
        sample_rate_hz=2,
        model_name="tribev2",
        metadata_json={"surface": "fsaverage5"},
    )

    processed = await complete_job_from_cached_result(session, job.id, cached, broker)

    assert processed is job
    assert job.status == JobStatus.complete
    assert len(session.added) == 1
    assert session.added[0].s3_key == "results/cached/activations.npz"
    assert session.added[0].metadata_json["cache_hit"] is True
    assert [event for _, event, _ in broker.events] == ["queued", "progress", "complete"]
    assert broker.events[-1][2] == {
        "job_id": str(job.id),
        "status": "complete",
        "result_s3_key": "results/cached/activations.npz",
        "timesteps": 4,
        "vertex_count": 20484,
    }


@pytest.mark.asyncio
async def test_run_inference_rejects_invalid_job_id():
    with pytest.raises(JobProcessingError) as exc:
        await _run_inference("not-a-uuid")

    assert "Invalid job id" in str(exc.value)
