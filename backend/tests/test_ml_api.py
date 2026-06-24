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
