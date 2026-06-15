from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app
from app.models.job import JobStatus
from app.services.sse_broker import JobStreamEvent, get_job_event_broker


def make_token() -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "supabase-user-123",
            "email": "researcher@example.com",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )


def make_user():
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        supabase_user_id="supabase-user-123",
        email="researcher@example.com",
        display_name=None,
        avatar_url=None,
        created_at=now,
        updated_at=now,
        last_seen_at=now,
    )


def make_job(owner_id, experiment_id=None, **overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "experiment_id": experiment_id or uuid4(),
        "owner_id": owner_id,
        "status": JobStatus.queued,
        "run_spec": {"blocks": [], "settings": {"surface": "fsaverage5"}},
        "error_code": None,
        "error_message": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_result(owner_id, job_id=None, experiment_id=None, **overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "job_id": job_id or uuid4(),
        "experiment_id": experiment_id or uuid4(),
        "owner_id": owner_id,
        "s3_key": "results/job-1/activations.npz",
        "format": "npz",
        "dtype": "float32",
        "shape": [4, 20484],
        "vertex_count": 20484,
        "timestep_count": 4,
        "sample_rate_hz": 2.0,
        "model_name": "tribev2",
        "model_version": "v2",
        "metadata_json": {"surface": "fsaverage5"},
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture
def auth_user(monkeypatch):
    user = make_user()

    async def fake_get_or_create_user_from_claims(session, claims):
        assert claims["sub"] == "supabase-user-123"
        return user

    monkeypatch.setattr("app.services.auth.get_or_create_user_from_claims", fake_get_or_create_user_from_claims)
    return user


@pytest.mark.asyncio
async def test_get_job_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{uuid4()}")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_job(auth_user, monkeypatch):
    job = make_job(auth_user.id)

    async def fake_get_owned_job(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job.id
        return job

    monkeypatch.setattr("app.api.jobs.get_owned_job", fake_get_owned_job)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/jobs/{job.id}",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(job.id)
    assert response.json()["status"] == "queued"
    assert response.json()["run_spec"] == job.run_spec


@pytest.mark.asyncio
async def test_get_job_result(auth_user, monkeypatch):
    job_id = uuid4()
    result = make_result(auth_user.id, job_id=job_id)

    async def fake_get_result_for_owned_job(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job_id
        return result

    monkeypatch.setattr("app.api.jobs.get_result_for_owned_job", fake_get_result_for_owned_job)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/jobs/{job_id}/result",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(result.id)
    assert payload["job_id"] == str(job_id)
    assert payload["s3_key"] == "results/job-1/activations.npz"
    assert payload["shape"] == [4, 20484]
    assert payload["vertex_count"] == 20484
    assert payload["timestep_count"] == 4
    assert payload["sample_rate_hz"] == 2.0
    assert payload["model_name"] == "tribev2"
    assert payload["metadata_json"] == {"surface": "fsaverage5"}


@pytest.mark.asyncio
async def test_cancel_job_marks_job_cancelled_and_publishes_sse(auth_user, monkeypatch):
    job = make_job(auth_user.id, status=JobStatus.running)

    async def fake_cancel_owned_job(session, owner, requested_job_id, broker):
        assert owner.id == auth_user.id
        assert requested_job_id == job.id
        assert broker is not None
        job.status = JobStatus.cancelled
        return job

    class FakeBroker:
        pass

    monkeypatch.setattr("app.api.jobs.cancel_owned_job", fake_cancel_owned_job)
    app.dependency_overrides[get_job_event_broker] = lambda: FakeBroker()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/jobs/{job.id}/cancel",
                headers={"Authorization": f"Bearer {make_token()}"},
            )
    finally:
        app.dependency_overrides.pop(get_job_event_broker, None)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_get_job_result_download(auth_user, monkeypatch):
    job_id = uuid4()
    result = make_result(auth_user.id, job_id=job_id)

    async def fake_get_result_for_owned_job(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job_id
        return result

    monkeypatch.setattr("app.api.jobs.get_result_for_owned_job", fake_get_result_for_owned_job)
    monkeypatch.setattr("app.api.jobs.create_result_download_url", lambda s3_key: f"https://s3.example/{s3_key}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/jobs/{job_id}/result/download",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "result_id": str(result.id),
        "job_id": str(job_id),
        "download_url": "https://s3.example/results/job-1/activations.npz",
        "expires_in_seconds": 900,
    }


@pytest.mark.asyncio
async def test_get_job_result_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{uuid4()}/result")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stream_job_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/jobs/{uuid4()}/stream")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stream_job_uses_persisted_job_status(auth_user, monkeypatch):
    job = make_job(auth_user.id)

    async def fake_get_owned_job(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job.id
        return job

    class FakeBroker:
        async def subscribe(self, job_id, after_event_id=None):
            assert job_id == job.id
            assert after_event_id is None
            yield JobStreamEvent(
                id=7,
                event="queued",
                data={"job_id": str(job.id), "status": "queued"},
            )

    monkeypatch.setattr("app.api.jobs.get_owned_job", fake_get_owned_job)
    app.dependency_overrides[get_job_event_broker] = lambda: FakeBroker()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/jobs/{job.id}/stream",
                headers={"Authorization": f"Bearer {make_token()}"},
            )
    finally:
        app.dependency_overrides.pop(get_job_event_broker, None)

    assert response.status_code == 200
    assert "event: queued\nid: 7\n" in response.text
    assert f'"job_id":"{job.id}"' in response.text
    assert '"status":"queued"' in response.text


@pytest.mark.asyncio
async def test_stream_job_honors_last_event_id(auth_user, monkeypatch):
    job = make_job(auth_user.id)

    async def fake_get_owned_job(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job.id
        return job

    class FakeBroker:
        async def subscribe(self, job_id, after_event_id=None):
            assert job_id == job.id
            assert after_event_id == 4
            yield JobStreamEvent(id=5, event="progress", data={"job_id": str(job.id), "completed_timesteps": 2})

    monkeypatch.setattr("app.api.jobs.get_owned_job", fake_get_owned_job)
    app.dependency_overrides[get_job_event_broker] = lambda: FakeBroker()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/jobs/{job.id}/stream",
                headers={"Authorization": f"Bearer {make_token()}", "Last-Event-ID": "4"},
            )
    finally:
        app.dependency_overrides.pop(get_job_event_broker, None)

    assert response.status_code == 200
    assert "id: 5" in response.text


@pytest.mark.asyncio
async def test_stream_job_closes_after_terminal_event(auth_user, monkeypatch):
    job = make_job(auth_user.id)

    async def fake_get_owned_job(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job.id
        return job

    class FakeBroker:
        async def subscribe(self, job_id, after_event_id=None):
            assert job_id == job.id
            yield JobStreamEvent(id=1, event="progress", data={"job_id": str(job.id), "completed_timesteps": 1})
            yield JobStreamEvent(
                id=2,
                event="complete",
                data={
                    "job_id": str(job.id),
                    "status": "complete",
                    "result_s3_key": None,
                    "timesteps": 1,
                    "vertex_count": 16,
                },
            )
            yield JobStreamEvent(id=3, event="progress", data={"job_id": str(job.id), "completed_timesteps": 2})

    monkeypatch.setattr("app.api.jobs.get_owned_job", fake_get_owned_job)
    app.dependency_overrides[get_job_event_broker] = lambda: FakeBroker()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/jobs/{job.id}/stream",
                headers={"Authorization": f"Bearer {make_token()}"},
            )
    finally:
        app.dependency_overrides.pop(get_job_event_broker, None)

    assert response.status_code == 200
    assert "event: complete" in response.text
    assert "id: 3" not in response.text


@pytest.mark.asyncio
async def test_list_experiment_jobs(auth_user, monkeypatch):
    experiment_id = uuid4()
    job = make_job(auth_user.id, experiment_id=experiment_id)

    async def fake_list_jobs_for_experiment(session, owner, requested_experiment_id):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        return [job]

    monkeypatch.setattr("app.api.experiments.list_jobs_for_experiment", fake_list_jobs_for_experiment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/experiments/{experiment_id}/jobs",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(job.id)
    assert response.json()[0]["experiment_id"] == str(experiment_id)
