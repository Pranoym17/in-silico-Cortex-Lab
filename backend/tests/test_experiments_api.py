from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app
from app.models.experiment import ExperimentStatus
from app.models.job import JobStatus


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


def make_experiment(owner_id: UUID, **overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "owner_id": owner_id,
        "name": "FFA pilot",
        "description": "Faces versus houses",
        "status": ExperimentStatus.draft,
        "is_public": False,
        "slug": None,
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def make_library_entry(owner_id: UUID, experiment_id: UUID, **overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "experiment_id": experiment_id,
        "owner_id": owner_id,
        "slug": "ffa-face-localizer",
        "title": "FFA face localizer",
        "description": "Faces versus houses",
        "tags": ["vision", "faces"],
        "featured": False,
        "run_count": 0,
        "published_at": now,
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
async def test_create_experiment_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/experiments", json={"name": "FFA pilot"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_experiment(auth_user, monkeypatch):
    async def fake_create_experiment(session, owner, data):
        assert owner.id == auth_user.id
        assert data.name == "FFA pilot"
        return make_experiment(auth_user.id, name=data.name, description=data.description)

    monkeypatch.setattr("app.api.experiments.create_experiment", fake_create_experiment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/experiments",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={"name": "FFA pilot", "description": "Faces versus houses"},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "FFA pilot"
    assert response.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_list_experiments(auth_user, monkeypatch):
    async def fake_list_experiments(session, owner):
        assert owner.id == auth_user.id
        return [make_experiment(auth_user.id)]

    monkeypatch.setattr("app.api.experiments.list_experiments", fake_list_experiments)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/experiments", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "FFA pilot"


@pytest.mark.asyncio
async def test_get_experiment_not_found(auth_user, monkeypatch):
    async def fake_get_owned_experiment(session, owner, experiment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

    monkeypatch.setattr("app.api.experiments.get_owned_experiment", fake_get_owned_experiment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/experiments/{uuid4()}", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Experiment not found"}


@pytest.mark.asyncio
async def test_update_experiment(auth_user, monkeypatch):
    experiment_id = uuid4()

    async def fake_update_experiment(session, owner, requested_experiment_id, data):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        assert data.name == "Updated pilot"
        return make_experiment(auth_user.id, id=experiment_id, name=data.name)

    monkeypatch.setattr("app.api.experiments.update_experiment", fake_update_experiment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/experiments/{experiment_id}",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={"name": "Updated pilot"},
        )

    assert response.status_code == 200
    assert response.json()["id"] == str(experiment_id)
    assert response.json()["name"] == "Updated pilot"


@pytest.mark.asyncio
async def test_delete_experiment_archives(auth_user, monkeypatch):
    experiment_id = uuid4()
    archived_ids = []

    async def fake_archive_experiment(session, owner, requested_experiment_id):
        assert owner.id == auth_user.id
        archived_ids.append(requested_experiment_id)

    monkeypatch.setattr("app.api.experiments.archive_experiment", fake_archive_experiment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            f"/api/experiments/{experiment_id}",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 204
    assert archived_ids == [experiment_id]


@pytest.mark.asyncio
async def test_publish_experiment_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/experiments/{uuid4()}/publish",
            json={"title": "FFA face localizer", "slug": "ffa-face-localizer"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_publish_experiment(auth_user, monkeypatch):
    experiment_id = uuid4()

    async def fake_publish_experiment(session, owner, requested_experiment_id, data):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        assert data.title == "FFA face localizer"
        assert data.slug == "ffa-face-localizer"
        assert data.tags == ["Vision", "faces"]
        return make_library_entry(auth_user.id, experiment_id, title=data.title, slug=data.slug, tags=["vision", "faces"])

    monkeypatch.setattr("app.api.experiments.publish_experiment", fake_publish_experiment)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/experiments/{experiment_id}/publish",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "title": "FFA face localizer",
                "description": "Faces versus houses",
                "slug": "ffa-face-localizer",
                "tags": ["Vision", "faces"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == str(experiment_id)
    assert body["slug"] == "ffa-face-localizer"
    assert body["tags"] == ["vision", "faces"]


@pytest.mark.asyncio
async def test_run_experiment_creates_persisted_job(auth_user, monkeypatch):
    experiment_id = uuid4()
    job_id = uuid4()
    dispatched_ids = []

    async def fake_create_job_from_experiment(session, owner, requested_experiment_id, settings):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        assert settings.surface == "fsaverage5"
        return SimpleNamespace(
            id=job_id,
            experiment_id=experiment_id,
            status=JobStatus.queued,
            run_spec={"blocks": [{"type": "text", "content_hash": "sha256:abc123"}]},
        )

    monkeypatch.setattr("app.api.experiments.create_job_from_experiment", fake_create_job_from_experiment)
    monkeypatch.setattr("app.api.experiments.get_cached_result", lambda content_hash, context=None: None)
    monkeypatch.setattr(
        "app.api.experiments.dispatch_inference_job",
        lambda background_tasks, dispatched_job_id: dispatched_ids.append(dispatched_job_id),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/experiments/{experiment_id}/run",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "blocks": [
                    {
                        "id": str(uuid4()),
                        "type": "text",
                        "condition": "faces",
                        "start_ms": 0,
                        "duration_ms": 1000,
                        "content_hash": "sha256:abc123",
                        "text": "face",
                    }
                ]
            },
        )

    assert response.status_code == 202
    assert response.json() == {
        "job_id": str(job_id),
        "experiment_id": str(experiment_id),
        "status": "queued",
        "stream_url": f"/api/jobs/{job_id}/stream",
        "user_id": str(auth_user.id),
    }
    assert dispatched_ids == [job_id]


@pytest.mark.asyncio
async def test_run_experiment_completes_from_cache_without_dispatch(auth_user, monkeypatch):
    experiment_id = uuid4()
    job_id = uuid4()
    dispatched_ids = []
    completed_ids = []
    cached_result = SimpleNamespace(s3_key="results/cached/activations.npz")
    job = SimpleNamespace(
        id=job_id,
        experiment_id=experiment_id,
        status=JobStatus.queued,
        run_spec={"blocks": [{"type": "text", "content_hash": "sha256:abc123"}]},
    )

    async def fake_create_job_from_experiment(session, owner, requested_experiment_id, settings):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        return job

    async def fake_complete_job_from_cached_result(session, completed_job_id, requested_cached_result):
        assert requested_cached_result is cached_result
        completed_ids.append(completed_job_id)
        job.status = JobStatus.complete

    monkeypatch.setattr("app.api.experiments.create_job_from_experiment", fake_create_job_from_experiment)
    monkeypatch.setattr("app.api.experiments.get_cached_result", lambda content_hash, context=None: cached_result)
    monkeypatch.setattr("app.api.experiments.result_artifact_exists", lambda s3_key: True)
    monkeypatch.setattr("app.api.experiments.complete_job_from_cached_result", fake_complete_job_from_cached_result)
    monkeypatch.setattr(
        "app.api.experiments.dispatch_inference_job",
        lambda background_tasks, dispatched_job_id: dispatched_ids.append(dispatched_job_id),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/experiments/{experiment_id}/run",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "blocks": [
                    {
                        "id": str(uuid4()),
                        "type": "text",
                        "condition": "faces",
                        "start_ms": 0,
                        "duration_ms": 1000,
                        "content_hash": "sha256:abc123",
                        "text": "face",
                    }
                ]
            },
        )

    assert response.status_code == 202
    assert response.json()["status"] == "complete"
    assert completed_ids == [job_id]
    assert dispatched_ids == []


@pytest.mark.asyncio
async def test_get_run_cache_hit_evicts_cached_result_when_s3_artifact_is_missing(monkeypatch):
    from app.api.experiments import get_run_cache_hit

    deleted = []
    cached_result = SimpleNamespace(s3_key="results/missing/activations.npz")
    monkeypatch.setattr("app.api.experiments.get_cached_result", lambda content_hash, context=None: cached_result)
    monkeypatch.setattr("app.api.experiments.result_artifact_exists", lambda s3_key: False)
    monkeypatch.setattr("app.api.experiments.delete_cached_result", lambda content_hash, context=None: deleted.append(content_hash))

    assert await get_run_cache_hit({"blocks": [{"type": "text", "content_hash": "sha256:abc"}]}) is None
    assert len(deleted) == 1
    assert deleted[0].startswith("sha256:")
    assert deleted[0] != "sha256:abc"


@pytest.mark.asyncio
async def test_get_run_cache_hit_treats_s3_check_failure_as_cache_miss(monkeypatch):
    from app.api.experiments import get_run_cache_hit
    from app.services.result_storage import ResultStorageError

    cached_result = SimpleNamespace(s3_key="results/job-1/activations.npz")
    monkeypatch.setattr("app.api.experiments.get_cached_result", lambda content_hash, context=None: cached_result)

    def raise_result_storage_error(s3_key):
        raise ResultStorageError("s3 down")

    monkeypatch.setattr("app.api.experiments.result_artifact_exists", raise_result_storage_error)

    assert await get_run_cache_hit({"blocks": [{"type": "text", "content_hash": "sha256:abc"}]}) is None
