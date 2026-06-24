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
