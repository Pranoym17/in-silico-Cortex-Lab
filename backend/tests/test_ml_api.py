from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app


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


@pytest.fixture
def auth_user(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        supabase_user_id="supabase-user-123",
        email="researcher@example.com",
        display_name=None,
        avatar_url=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    async def fake_get_or_create_user_from_claims(session, claims):
        return user

    monkeypatch.setattr("app.services.auth.get_or_create_user_from_claims", fake_get_or_create_user_from_claims)
    return user


@pytest.mark.asyncio
async def test_ml_health_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/ml/health")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ml_health(auth_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/ml/health", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "surface": "ml"}


@pytest.mark.asyncio
async def test_run_rsa_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/ml/rsa", json={"job_id_a": str(uuid4()), "job_id_b": str(uuid4())})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_run_rsa(auth_user, monkeypatch):
    job_id_a = uuid4()
    job_id_b = uuid4()

    async def fake_run_rsa(session, owner, body):
        assert owner.id == auth_user.id
        assert body.job_id_a == job_id_a
        assert body.job_id_b == job_id_b
        return {
            "job_id_a": job_id_a,
            "job_id_b": job_id_b,
            "rsa_score": 1.0,
            "rdm_a": [[0.0, 1.0], [1.0, 0.0]],
            "rdm_b": [[0.0, 1.0], [1.0, 0.0]],
            "labels_a": ["a", "b"],
            "labels_b": ["a", "b"],
            "mds_a": [{"x": -0.5, "y": 0.0, "label": "a", "index": 0}, {"x": 0.5, "y": 0.0, "label": "b", "index": 1}],
            "mds_b": [{"x": -0.5, "y": 0.0, "label": "a", "index": 0}, {"x": 0.5, "y": 0.0, "label": "b", "index": 1}],
            "block_count": 2,
            "vertex_count": 20484,
        }

    monkeypatch.setattr("app.api.ml.run_rsa", fake_run_rsa)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/ml/rsa",
            json={"job_id_a": str(job_id_a), "job_id_b": str(job_id_b)},
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert response.json()["rsa_score"] == 1.0
    assert response.json()["labels_a"] == ["a", "b"]


@pytest.mark.asyncio
async def test_get_cognitive_states_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/ml/jobs/{uuid4()}/cognitive-states")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_cognitive_states(auth_user, monkeypatch):
    job_id = uuid4()

    async def fake_get_cognitive_states(session, owner, requested_job_id):
        assert owner.id == auth_user.id
        assert requested_job_id == job_id
        return {
            "job_id": job_id,
            "classifier_version": "rules-v1",
            "states": [
                {
                    "timestep": 0,
                    "label": "Language Comprehension",
                    "confidence": 0.8,
                    "scores": {"Language Comprehension": 0.8, "Rest / Low Activation": 0.2},
                }
            ],
        }

    monkeypatch.setattr("app.api.ml.get_cognitive_states", fake_get_cognitive_states)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/ml/jobs/{job_id}/cognitive-states",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert response.json()["classifier_version"] == "rules-v1"
    assert response.json()["states"][0]["label"] == "Language Comprehension"


@pytest.mark.asyncio
async def test_start_optimizer_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/ml/optimize",
            json={"target_region": "Left Fusiform", "direction": "maximize"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_start_optimizer(auth_user, monkeypatch):
    optimizer_job_id = uuid4()

    def fake_start_optimizer_job(body):
        assert body.target_region == "Left Fusiform"
        return {
            "optimizer_job_id": optimizer_job_id,
            "status": "complete",
            "stream_url": f"/api/ml/optimize/{optimizer_job_id}/stream",
        }

    monkeypatch.setattr("app.api.ml.start_optimizer_job", fake_start_optimizer_job)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/ml/optimize",
            json={"target_region": "Left Fusiform", "direction": "maximize"},
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 202
    assert response.json()["optimizer_job_id"] == str(optimizer_job_id)


@pytest.mark.asyncio
async def test_stream_optimizer(auth_user, monkeypatch):
    optimizer_job_id = uuid4()

    class FakeRecord:
        events = [
            ("queued", {"optimizer_job_id": str(optimizer_job_id), "status": "queued"}),
            ("complete", {"optimizer_job_id": str(optimizer_job_id), "status": "complete"}),
        ]

    monkeypatch.setattr("app.api.ml.get_optimizer_job", lambda requested_id: FakeRecord() if requested_id == optimizer_job_id else None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/ml/optimize/{optimizer_job_id}/stream",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert "event: queued" in response.text
    assert "event: complete" in response.text
