from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.block import BlockCreate, BlockReorderRequest, BlockResponse, BlockUpdate
from app.schemas.experiment import ExperimentCreate, ExperimentResponse, ExperimentUpdate
from app.schemas.run import RunExperimentRequest, RunExperimentResponse
from app.services.blocks import create_block, delete_block, list_blocks, reorder_blocks, update_block
from app.services.experiments import (
    archive_experiment,
    create_experiment,
    get_owned_experiment,
    list_experiments,
    update_experiment,
)

router = APIRouter()


@router.post("", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def create_experiment_route(
    body: ExperimentCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await create_experiment(session, user, body)


@router.get("", response_model=list[ExperimentResponse])
async def list_experiments_route(
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await list_experiments(session, user)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment_route(
    experiment_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await get_owned_experiment(session, user, experiment_id)


@router.patch("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment_route(
    experiment_id: UUID,
    body: ExperimentUpdate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await update_experiment(session, user, experiment_id, body)


@router.delete("/{experiment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experiment_route(
    experiment_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    await archive_experiment(session, user, experiment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{experiment_id}/blocks", response_model=list[BlockResponse])
async def list_blocks_route(
    experiment_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await list_blocks(session, user, experiment_id)


@router.post("/{experiment_id}/blocks", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
async def create_block_route(
    experiment_id: UUID,
    body: BlockCreate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await create_block(session, user, experiment_id, body)


@router.patch("/{experiment_id}/blocks/{block_id}", response_model=BlockResponse)
async def update_block_route(
    experiment_id: UUID,
    block_id: UUID,
    body: BlockUpdate,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await update_block(session, user, experiment_id, block_id, body)


@router.delete("/{experiment_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_route(
    experiment_id: UUID,
    block_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    await delete_block(session, user, experiment_id, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{experiment_id}/blocks/reorder", response_model=list[BlockResponse])
async def reorder_blocks_route(
    experiment_id: UUID,
    body: BlockReorderRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await reorder_blocks(session, user, experiment_id, body)


@router.post("/{experiment_id}/run", response_model=RunExperimentResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_experiment(
    experiment_id: str,
    body: RunExperimentRequest,
    user: User = Depends(require_user),
) -> RunExperimentResponse:
    job_id = f"job_local_{experiment_id}"
    # Persistence and Celery enqueueing will be wired after the database layer lands.
    return RunExperimentResponse(
        job_id=job_id,
        experiment_id=experiment_id,
        status="queued",
        stream_url=f"/api/jobs/{job_id}/stream",
        user_id=str(user.id),
    )
