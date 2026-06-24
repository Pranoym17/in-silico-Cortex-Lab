from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ml import CognitiveStatesResponse, OptimizerRequest, OptimizerStartResponse, RsaRequest, RsaResponse
from app.services.ml_cognitive_states import get_cognitive_states
from app.services.ml_optimizer import get_optimizer_job, start_optimizer_job
from app.services.ml_rsa import run_rsa
from app.services.sse import encode_sse

router = APIRouter()


@router.get("/health")
async def ml_health(_: User = Depends(require_user)) -> dict[str, str]:
    return {"status": "ok", "surface": "ml"}


@router.post("/rsa", response_model=RsaResponse)
async def run_rsa_route(
    body: RsaRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> RsaResponse:
    return await run_rsa(session, user, body)


@router.get("/jobs/{job_id}/cognitive-states", response_model=CognitiveStatesResponse)
async def get_cognitive_states_route(
    job_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> CognitiveStatesResponse:
    return await get_cognitive_states(session, user, job_id)


@router.post("/optimize", response_model=OptimizerStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_optimizer_route(
    body: OptimizerRequest,
    _: User = Depends(require_user),
) -> OptimizerStartResponse:
    return start_optimizer_job(body)


@router.get("/optimize/{optimizer_job_id}/stream")
async def stream_optimizer_route(
    optimizer_job_id: UUID,
    _: User = Depends(require_user),
) -> StreamingResponse:
    record = get_optimizer_job(optimizer_job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimizer job not found")

    async def events():
        for index, (event_name, data) in enumerate(record.events, start=1):
            yield encode_sse(event_name, data, event_id=index)

    return StreamingResponse(events(), media_type="text/event-stream")
