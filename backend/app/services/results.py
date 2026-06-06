from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.result import Result
from app.models.user import User
from app.services.jobs import get_owned_job


async def get_result_for_owned_job(session: AsyncSession, owner: User, job_id: UUID) -> Result:
    await get_owned_job(session, owner, job_id)
    result = await session.execute(
        select(Result)
        .where(Result.job_id == job_id)
        .where(Result.owner_id == owner.id)
        .order_by(Result.created_at.desc())
        .limit(1)
    )
    job_result = result.scalar_one_or_none()
    if job_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return job_result
