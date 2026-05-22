import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobResponse
from app.services.jobs import get_owned_job
from app.services.sse import encode_sse

router = APIRouter()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_route(
    job_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await get_owned_job(session, user, job_id)


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: UUID,
    from_timestep: int = 0,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    job = await get_owned_job(session, user, job_id)

    async def events():
        yield encode_sse("queued", {"job_id": str(job.id), "status": job.status.value}, event_id=1)
        await asyncio.sleep(0.05)
        yield encode_sse(
            "warming",
            {"job_id": str(job.id), "reason": "modal_cold_start", "estimated_seconds": 90},
            event_id=2,
        )
        await asyncio.sleep(0.05)
        yield encode_sse(
            "progress",
            {
                "job_id": str(job.id),
                "completed_blocks": 0,
                "total_blocks": 0,
                "completed_timesteps": from_timestep,
            },
            event_id=3,
        )

    return StreamingResponse(events(), media_type="text/event-stream")
