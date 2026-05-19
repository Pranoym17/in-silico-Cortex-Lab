from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import get_settings
from app.main import app
from app.models.block import BlockType


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


def make_block(experiment_id: UUID, **overrides):
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "experiment_id": experiment_id,
        "type": BlockType.text,
        "condition": "language",
        "start_ms": 0,
        "duration_ms": 5000,
        "content_hash": None,
        "payload": {"text": "The dog chased the ball.", "voice": "kokoro_default"},
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
async def test_list_blocks_requires_authentication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/experiments/{uuid4()}/blocks")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_block(auth_user, monkeypatch):
    experiment_id = uuid4()

    async def fake_create_block(session, owner, requested_experiment_id, data):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        assert data.type == BlockType.text
        return make_block(experiment_id, type=data.type, duration_ms=data.duration_ms, payload=data.payload)

    monkeypatch.setattr("app.api.experiments.create_block", fake_create_block)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/experiments/{experiment_id}/blocks",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={
                "type": "text",
                "condition": "language",
                "start_ms": 0,
                "duration_ms": 5000,
                "payload": {"text": "The dog chased the ball.", "voice": "kokoro_default"},
            },
        )

    assert response.status_code == 201
    assert response.json()["type"] == "text"
    assert response.json()["payload"]["voice"] == "kokoro_default"


@pytest.mark.asyncio
async def test_list_blocks(auth_user, monkeypatch):
    experiment_id = uuid4()

    async def fake_list_blocks(session, owner, requested_experiment_id):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        return [make_block(experiment_id)]

    monkeypatch.setattr("app.api.experiments.list_blocks", fake_list_blocks)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/experiments/{experiment_id}/blocks",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["condition"] == "language"


@pytest.mark.asyncio
async def test_update_block(auth_user, monkeypatch):
    experiment_id = uuid4()
    block_id = uuid4()

    async def fake_update_block(session, owner, requested_experiment_id, requested_block_id, data):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        assert requested_block_id == block_id
        assert data.duration_ms == 7000
        return make_block(experiment_id, id=block_id, duration_ms=data.duration_ms)

    monkeypatch.setattr("app.api.experiments.update_block", fake_update_block)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/experiments/{experiment_id}/blocks/{block_id}",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={"duration_ms": 7000},
        )

    assert response.status_code == 200
    assert response.json()["duration_ms"] == 7000


@pytest.mark.asyncio
async def test_delete_block(auth_user, monkeypatch):
    experiment_id = uuid4()
    block_id = uuid4()
    deleted_ids = []

    async def fake_delete_block(session, owner, requested_experiment_id, requested_block_id):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        deleted_ids.append(requested_block_id)

    monkeypatch.setattr("app.api.experiments.delete_block", fake_delete_block)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(
            f"/api/experiments/{experiment_id}/blocks/{block_id}",
            headers={"Authorization": f"Bearer {make_token()}"},
        )

    assert response.status_code == 204
    assert deleted_ids == [block_id]


@pytest.mark.asyncio
async def test_reorder_blocks(auth_user, monkeypatch):
    experiment_id = uuid4()
    block_id = uuid4()

    async def fake_reorder_blocks(session, owner, requested_experiment_id, data):
        assert owner.id == auth_user.id
        assert requested_experiment_id == experiment_id
        assert data.blocks[0].id == block_id
        return [make_block(experiment_id, id=block_id, start_ms=2000, duration_ms=3000)]

    monkeypatch.setattr("app.api.experiments.reorder_blocks", fake_reorder_blocks)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.put(
            f"/api/experiments/{experiment_id}/blocks/reorder",
            headers={"Authorization": f"Bearer {make_token()}"},
            json={"blocks": [{"id": str(block_id), "start_ms": 2000, "duration_ms": 3000}]},
        )

    assert response.status_code == 200
    assert response.json()[0]["start_ms"] == 2000

