import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.api.health import database_health
from app.main import app


@pytest.mark.asyncio
async def test_health_route_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_database_health_executes_probe():
    class FakeSession:
        def __init__(self) -> None:
            self.statement = None

        async def execute(self, statement):
            self.statement = statement

    session = FakeSession()
    response = await database_health(session)  # type: ignore[arg-type]

    assert response == {"status": "ok", "database": "ok"}
    assert str(session.statement) == str(text("select 1"))


@pytest.mark.asyncio
async def test_database_health_raises_503_on_failure():
    class FailingSession:
        async def execute(self, statement):
            raise RuntimeError("database down")

    with pytest.raises(HTTPException) as exc:
        await database_health(FailingSession())  # type: ignore[arg-type]

    assert exc.value.status_code == 503
    assert exc.value.detail == "Database unavailable"

