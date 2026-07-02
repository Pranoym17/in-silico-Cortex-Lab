from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def _extract_metadata(claims: dict[str, Any]) -> dict[str, Any]:
    metadata = claims.get("user_metadata")
    return metadata if isinstance(metadata, dict) else {}


async def get_or_create_user_from_claims(session: AsyncSession, claims: dict[str, Any]) -> User:
    supabase_user_id = str(claims["sub"])
    result = await session.execute(select(User).where(User.supabase_user_id == supabase_user_id))
    user = result.scalar_one_or_none()

    metadata = _extract_metadata(claims)
    email = claims.get("email")
    display_name = metadata.get("full_name") or metadata.get("name")
    avatar_url = metadata.get("avatar_url") or metadata.get("picture")

    created = user is None
    if created:
        user = User(
            supabase_user_id=supabase_user_id,
            email=email,
            display_name=display_name,
            avatar_url=avatar_url,
        )
        session.add(user)
    else:
        user.email = email or user.email
        user.display_name = display_name or user.display_name
        user.avatar_url = avatar_url or user.avatar_url

    user.last_seen_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError:
        if not created:
            raise
        await session.rollback()
        result = await session.execute(select(User).where(User.supabase_user_id == supabase_user_id))
        user = result.scalar_one()
        user.email = email or user.email
        user.display_name = display_name or user.display_name
        user.avatar_url = avatar_url or user.avatar_url
        user.last_seen_at = datetime.now(UTC)
        await session.commit()
    await session.refresh(user)
    return user

