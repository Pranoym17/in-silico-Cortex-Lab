import asyncio
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.block import BlockCreate, BlockReorderRequest, BlockResponse, BlockUpdate
from app.schemas.experiment import ExperimentCreate, ExperimentResponse, ExperimentUpdate
from app.schemas.job import JobResponse
from app.schemas.library import LibraryEntryResponse, LibraryPublishRequest
from app.schemas.run import RunExperimentRequest, RunExperimentResponse
from app.services.blocks import create_block, delete_block, list_blocks, reorder_blocks, update_block
from app.services.experiments import (
    archive_experiment,
    create_experiment,
    get_owned_experiment,
    list_experiments,
    update_experiment,
)
from app.services.job_dispatch import dispatch_inference_job
from app.services.jobs import create_job_from_experiment, list_jobs_for_experiment
from app.services.library import publish_experiment
from app.services.result_cache import delete_cached_result, get_cached_result, run_result_cache_identity
from app.services.result_storage import ResultStorageError, result_artifact_exists
from app.services.job_processing import complete_job_from_cached_result

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


@router.post("/{experiment_id}/publish", response_model=LibraryEntryResponse)
async def publish_experiment_route(
    experiment_id: UUID,
    body: LibraryPublishRequest,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await publish_experiment(session, user, experiment_id, body)


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
    experiment_id: UUID,
    body: RunExperimentRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
) -> RunExperimentResponse:
    job = await create_job_from_experiment(session, user, experiment_id, body.settings)
    cached_result = await get_run_cache_hit(job.run_spec)
    if cached_result is not None:
        await complete_job_from_cached_result(session, job.id, cached_result)
    else:
        dispatch_inference_job(background_tasks, job.id)
    return RunExperimentResponse(
        job_id=str(job.id),
        experiment_id=str(job.experiment_id),
        status=job.status.value,
        stream_url=f"/api/jobs/{job.id}/stream",
        user_id=str(user.id),
    )


@router.get("/{experiment_id}/jobs", response_model=list[JobResponse])
async def list_experiment_jobs_route(
    experiment_id: UUID,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_db),
):
    return await list_jobs_for_experiment(session, user, experiment_id)


async def get_run_cache_hit(run_spec: dict):
    try:
        content_hash, context = run_result_cache_identity(run_spec, model_name="tribev2")
    except (TypeError, ValueError):
        return None
    cached = await asyncio.to_thread(get_cached_result, content_hash, context)
    if cached is None:
        return None

    try:
        if await asyncio.to_thread(result_artifact_exists, cached.s3_key):
            return cached
    except ResultStorageError:
        return None

    await asyncio.to_thread(delete_cached_result, content_hash, context)
    return None
