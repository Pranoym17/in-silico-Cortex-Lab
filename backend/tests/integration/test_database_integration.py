import os

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.block import Block
from app.models.experiment import Experiment, ExperimentStatus
from app.models.job import Job
from app.models.result import Result
from app.models.user import User
from app.schemas.experiment import ExperimentCreate, ExperimentUpdate
from app.services.experiments import (
    archive_experiment,
    create_experiment,
    get_owned_experiment,
    list_experiments,
    update_experiment,
)
from app.services.users import get_or_create_user_from_claims

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("CORTEX_RUN_DB_TESTS") != "1", reason="set CORTEX_RUN_DB_TESTS=1 to run DB tests"),
]


async def clear_database(session) -> None:
    for model in (Result, Job, Block, Experiment, User):
        await session.execute(delete(model))
    await session.commit()


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        await clear_database(session)
        yield session
        await clear_database(session)


@pytest.mark.asyncio
async def test_user_sync_creates_and_updates_local_user(db_session):
    claims = {
        "sub": "supabase-user-123",
        "email": "first@example.com",
        "user_metadata": {
            "full_name": "First Name",
            "avatar_url": "https://example.com/first.png",
        },
    }

    created = await get_or_create_user_from_claims(db_session, claims)

    assert created.supabase_user_id == "supabase-user-123"
    assert created.email == "first@example.com"
    assert created.display_name == "First Name"

    updated = await get_or_create_user_from_claims(
        db_session,
        {
            "sub": "supabase-user-123",
            "email": "second@example.com",
            "user_metadata": {"name": "Second Name"},
        },
    )

    assert updated.id == created.id
    assert updated.email == "second@example.com"
    assert updated.display_name == "Second Name"


@pytest.mark.asyncio
async def test_experiment_crud_enforces_owner_scope(db_session):
    owner = await get_or_create_user_from_claims(db_session, {"sub": "owner-123", "email": "owner@example.com"})
    other_user = await get_or_create_user_from_claims(db_session, {"sub": "other-123", "email": "other@example.com"})

    experiment = await create_experiment(
        db_session,
        owner,
        ExperimentCreate(name="FFA pilot", description="Faces versus houses"),
    )

    assert experiment.owner_id == owner.id
    assert experiment.status == ExperimentStatus.draft

    listed = await list_experiments(db_session, owner)
    assert [item.id for item in listed] == [experiment.id]

    loaded = await get_owned_experiment(db_session, owner, experiment.id)
    assert loaded.id == experiment.id

    with pytest.raises(HTTPException) as not_found:
        await get_owned_experiment(db_session, other_user, experiment.id)
    assert not_found.value.status_code == 404

    updated = await update_experiment(
        db_session,
        owner,
        experiment.id,
        ExperimentUpdate(name="Updated FFA pilot", status=ExperimentStatus.ready),
    )
    assert updated.name == "Updated FFA pilot"
    assert updated.status == ExperimentStatus.ready

    await archive_experiment(db_session, owner, experiment.id)
    listed_after_archive = await list_experiments(db_session, owner)
    assert listed_after_archive == []


@pytest.mark.asyncio
async def test_database_health_uses_live_database():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}

