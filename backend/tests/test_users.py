from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.users import get_or_create_user_from_claims


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        assert self.value is not None
        return self.value


@pytest.mark.asyncio
async def test_concurrent_first_request_recovers_existing_user():
    existing = SimpleNamespace(
        id=uuid4(),
        supabase_user_id="shared-user",
        email="original@example.com",
        display_name=None,
        avatar_url=None,
        last_seen_at=None,
    )

    class RacingSession:
        def __init__(self):
            self.execute_count = 0
            self.commit_count = 0
            self.rollback_count = 0
            self.refreshed = None

        async def execute(self, statement):
            self.execute_count += 1
            return ScalarResult(None if self.execute_count == 1 else existing)

        def add(self, user):
            return None

        async def commit(self):
            self.commit_count += 1
            if self.commit_count == 1:
                raise IntegrityError("insert user", {}, Exception("unique violation"))

        async def rollback(self):
            self.rollback_count += 1

        async def refresh(self, user):
            self.refreshed = user

    session = RacingSession()
    user = await get_or_create_user_from_claims(
        session,
        {
            "sub": "shared-user",
            "email": "latest@example.com",
            "user_metadata": {"name": "Latest User"},
        },
    )

    assert user is existing
    assert user.email == "latest@example.com"
    assert user.display_name == "Latest User"
    assert session.rollback_count == 1
    assert session.commit_count == 2
    assert session.refreshed is existing
