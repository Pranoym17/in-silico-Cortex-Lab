from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app
from app.schemas.upload import UploadIntentResponse


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
    now = datetime.now(UTC)
    user = SimpleNamespace(
        id=uuid4(),
        supabase_user_id="supabase-user-123",
        email="researcher@example.com",
        display_name=None,
        avatar_url=None,
        created_at=now,
        updated_at=now,
        last_seen_at=now,
    )

    async def fake_get_or_create_user_from_claims(session, claims):
        assert claims["sub"] == "supabase-user-123"
        return user

    monkeypatch.setattr("app.services.auth.get_or_create_user_from_claims", fake_get_or_create_user_from_claims)
    return user


@pytest.mark.asyncio
async def test_presign_upload_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/uploads/presign", json={})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_presign_upload_intent(auth_user, monkeypatch):
    experiment_id = uuid4()
    block_id = uuid4()

    def fake_create_upload_intent(owner, data):
        assert owner.id == auth_user.id
        assert data.experiment_id == experiment_id
        assert data.block_id == block_id
        assert data.kind == "image"
        return UploadIntentResponse(
            upload_url="https://s3.example/presigned",
            object_key=f"uploads/{owner.id}/experiments/{experiment_id}/{block_id}/face.png",
            headers={"Content-Type": data.mime_type},
            expires_in_seconds=900,
        )

    monkeypatch.setattr("app.api.uploads.create_upload_intent", fake_create_upload_intent)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/uploads/presign",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "experiment_id": str(experiment_id),
                "block_id": str(block_id),
                "kind": "image",
                "filename": "face.png",
                "mime_type": "image/png",
                "size_bytes": 512000,
            },
        )

    assert response.status_code == 201
    assert response.json()["upload_url"] == "https://s3.example/presigned"
    assert response.json()["headers"] == {"Content-Type": "image/png"}
    assert response.json()["content_hash_algorithm"] == "sha256"


@pytest.mark.asyncio
async def test_presign_upload_rejects_oversized_image(auth_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/uploads/presign",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "experiment_id": str(uuid4()),
                "kind": "image",
                "filename": "huge.webp",
                "mime_type": "image/webp",
                "size_bytes": 11 * 1024 * 1024,
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_presign_upload_maps_service_failure(auth_user, monkeypatch):
    def fail_create_upload_intent(owner, data):
        raise RuntimeError("raw aws stack trace")

    monkeypatch.setattr("app.api.uploads.create_upload_intent", fail_create_upload_intent)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/uploads/presign",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "experiment_id": str(uuid4()),
                "kind": "image",
                "filename": "face.png",
                "mime_type": "image/png",
                "size_bytes": 512000,
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "upload_failed",
            "message": "Upload setup failed. Check S3 configuration and retry.",
        }
    }
