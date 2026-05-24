from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import JobResponse
from app.services.jobs import get_owned_job
from app.services.sse_broker import JobEventBroker, get_job_event_broker
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
    from_event_id: int | None = None,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
    broker: JobEventBroker = Depends(get_job_event_broker),
) -> StreamingResponse:
    await get_owned_job(session, user, job_id)
    after_event_id = _resolve_after_event_id(from_event_id, last_event_id)

    async def events():
        async for stream_event in broker.subscribe(job_id, after_event_id=after_event_id):
            if stream_event.event == "progress" and from_timestep:
                if stream_event.data.get("completed_timesteps", 0) < from_timestep:
                    continue
            yield encode_sse(stream_event.event, stream_event.data, event_id=stream_event.id)
            if stream_event.event in {"complete", "error"}:
                break

    return StreamingResponse(events(), media_type="text/event-stream")


def _resolve_after_event_id(from_event_id: int | None, last_event_id: str | None) -> int | None:
    if from_event_id is not None:
        return from_event_id
    if last_event_id is None or not last_event_id.strip():
        return None
    try:
        return int(last_event_id)
    except ValueError:
        return None
