from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
import hashlib

from app.models.block import Block, BlockType
from app.models.experiment import Experiment
from app.schemas.ml import CognitiveStatesResponse, OptimizerJobStatusResponse, OptimizerRequest, OptimizerStartResponse, OptimizerWinnerExperimentResponse, RsaRequest, RsaResponse
from app.services.ml_cognitive_states import get_cognitive_states
from app.services.ml_optimizer import cancel_optimizer_job, get_optimizer_job, start_optimizer_job
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
    try:
        return start_optimizer_job(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


def optimizer_status_response(record) -> OptimizerJobStatusResponse:
    return OptimizerJobStatusResponse(
        optimizer_job_id=record.id,
        status=record.status,
        target_region=record.request.target_region,
        direction=record.request.direction,
        result=record.result,
    )


@router.get("/optimize/{optimizer_job_id}", response_model=OptimizerJobStatusResponse)
async def get_optimizer_route(optimizer_job_id: UUID, _: User = Depends(require_user)) -> OptimizerJobStatusResponse:
    record = get_optimizer_job(optimizer_job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimizer job not found")
    return optimizer_status_response(record)


@router.post("/optimize/{optimizer_job_id}/cancel", response_model=OptimizerJobStatusResponse)
async def cancel_optimizer_route(optimizer_job_id: UUID, _: User = Depends(require_user)) -> OptimizerJobStatusResponse:
    record = cancel_optimizer_job(optimizer_job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimizer job not found")
    return optimizer_status_response(record)


@router.post("/optimize/{optimizer_job_id}/winner-experiment", response_model=OptimizerWinnerExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_winner_experiment_route(
    optimizer_job_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> OptimizerWinnerExperimentResponse:
    record = get_optimizer_job(optimizer_job_id)
    if record is None or record.result is None or record.status != "complete":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Optimizer winner is not available")
    text = record.result.best_stimulus
    experiment = Experiment(owner_id=user.id, name=f"Optimizer: {record.request.target_region}", description="Draft created from a real TRIBE optimizer winner.")
    session.add(experiment)
    await session.flush()
    block = Block(
        experiment_id=experiment.id,
        type=BlockType.text,
        condition=f"Optimizer {record.request.direction}: {record.request.target_region}",
        start_ms=0,
        duration_ms=4_000,
        content_hash=f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
        payload={"text": text, "voice": "tribe_official_gtts", "optimizer_job_id": str(record.id), "optimizer_score": record.result.best_score},
    )
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return OptimizerWinnerExperimentResponse(experiment_id=experiment.id, block_id=block.id)


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
