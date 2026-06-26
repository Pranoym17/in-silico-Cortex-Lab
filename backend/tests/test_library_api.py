from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app
from app.schemas.library import LibraryDetailResponse, LibraryForkResponse, LibraryListResponse, PublicLibraryExperimentBlock


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


def make_library_entry(**overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "experiment_id": uuid4(),
        "owner_id": uuid4(),
        "slug": "ffa-face-localizer",
        "title": "FFA face localizer",
        "description": "Faces versus houses",
        "tags": ["vision", "faces"],
        "featured": True,
        "run_count": 7,
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
async def test_list_library_entries(monkeypatch):
    entry = make_library_entry()

    async def fake_list_library_entries(session, *, tag=None, search=None, sort="featured"):
        assert tag == "vision"
        assert search == "face"
        assert sort == "run_count"
        return LibraryListResponse(items=[entry])

    monkeypatch.setattr("app.api.library.list_library_entries", fake_list_library_entries)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/library?tag=vision&search=face&sort=run_count")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["slug"] == "ffa-face-localizer"
    assert body["items"][0]["featured"] is True


@pytest.mark.asyncio
async def test_get_library_detail(monkeypatch):
    entry = make_library_entry()
    block_id = uuid4()

    async def fake_get_library_detail(session, slug):
        assert slug == "ffa-face-localizer"
        return LibraryDetailResponse(
            entry=entry,
            experiment_name="FFA pilot",
            experiment_description="Faces versus houses",
            blocks=[
                PublicLibraryExperimentBlock(
                    id=block_id,
                    type="text",
                    condition="faces",
                    start_ms=0,
                    duration_ms=1000,
                    payload={"text": "face"},
                )
            ],
        )

    monkeypatch.setattr("app.api.library.get_library_detail", fake_get_library_detail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/library/ffa-face-localizer")

    assert response.status_code == 200
    body = response.json()
    assert body["entry"]["slug"] == "ffa-face-localizer"
    assert body["experiment_name"] == "FFA pilot"
    assert body["blocks"] == [
        {
            "id": str(block_id),
            "type": "text",
            "condition": "faces",
            "start_ms": 0,
            "duration_ms": 1000,
            "payload": {"text": "face"},
        }
    ]


@pytest.mark.asyncio
async def test_get_library_detail_not_found(monkeypatch):
    async def fake_get_library_detail(session, slug):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found")

    monkeypatch.setattr("app.api.library.get_library_detail", fake_get_library_detail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/library/missing-entry")

    assert response.status_code == 404
    assert response.json() == {"detail": "Library entry not found"}


@pytest.mark.asyncio
async def test_fork_library_entry_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/library/ffa-face-localizer/fork")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_fork_library_entry(auth_user, monkeypatch):
    experiment_id = uuid4()

    async def fake_fork_library_entry(session, owner, slug):
        assert owner.id == auth_user.id
        assert slug == "ffa-face-localizer"
        return LibraryForkResponse(experiment_id=experiment_id)

    monkeypatch.setattr("app.api.library.fork_library_entry", fake_fork_library_entry)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/library/ffa-face-localizer/fork",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert response.json() == {"experiment_id": str(experiment_id)}
