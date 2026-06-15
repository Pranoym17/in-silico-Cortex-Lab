from typing import Any
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block
from app.models.experiment import ExperimentStatus
from app.models.job import Job, JobStatus
from app.models.user import User
from app.schemas.sse import ErrorEvent
from app.schemas.run import RunExperimentRequest, RunSettings
from app.services.blocks import list_blocks
from app.services.experiments import get_owned_experiment
from app.services.sse_broker import JobEventBroker, get_job_event_broker


def _required_payload_string(block: Block, key: str, label: str) -> str:
    value = block.payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=label)
    return value


def _base_run_block(block: Block) -> dict[str, Any]:
    if not block.content_hash:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="all blocks require content_hash")

    return {
        "id": str(block.id),
        "type": block.type.value,
        "condition": block.condition,
        "start_ms": block.start_ms,
        "duration_ms": block.duration_ms,
        "content_hash": block.content_hash,
    }


def block_to_run_spec(block: Block) -> dict[str, Any]:
    base = _base_run_block(block)

    if block.type.value == "image":
        display = block.payload.get("display") if isinstance(block.payload.get("display"), dict) else {}
        return {
            **base,
            "s3_key": _required_payload_string(block, "s3_key", "image blocks require s3_key"),
            "mime_type": _required_payload_string(block, "mime_type", "image blocks require mime_type"),
            "display": {"mode": display.get("mode", "center")},
        }

    if block.type.value == "audio":
        return {
            **base,
            "s3_key": _required_payload_string(block, "s3_key", "audio blocks require s3_key"),
            "mime_type": _required_payload_string(block, "mime_type", "audio blocks require mime_type"),
            "channels": block.payload.get("channels", 1),
            "sample_rate_hz": block.payload.get("sample_rate_hz", 16000),
        }

    return {
        **base,
        "text": _required_payload_string(block, "text", "text blocks require text"),
        "voice": block.payload.get("voice", "kokoro_default"),
    }


async def create_job_from_experiment(
    session: AsyncSession,
    owner: User,
    experiment_id: UUID,
    settings: RunSettings | None = None,
) -> Job:
    experiment = await get_owned_experiment(session, owner, experiment_id)
    if experiment.status == ExperimentStatus.archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived experiments cannot be run")

    blocks = await list_blocks(session, owner, experiment_id)
    if not blocks:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="experiment has no blocks")

    request = RunExperimentRequest(
        blocks=[block_to_run_spec(block) for block in blocks],
        settings=settings or RunSettings(),
    )
    run_spec = request.model_dump(mode="json")
    job = Job(
        experiment_id=experiment_id,
        owner_id=owner.id,
        status=JobStatus.queued,
        run_spec=run_spec,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_owned_job(session: AsyncSession, owner: User, job_id: UUID) -> Job:
    result = await session.execute(select(Job).where(Job.id == job_id).where(Job.owner_id == owner.id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def cancel_owned_job(
    session: AsyncSession,
    owner: User,
    job_id: UUID,
    broker: JobEventBroker | None = None,
) -> Job:
    broker = broker or get_job_event_broker()
    job = await get_owned_job(session, owner, job_id)
    if job.status in {JobStatus.complete, JobStatus.failed, JobStatus.cancelled}:
        return job

    job.status = JobStatus.cancelled
    job.error_code = "cancelled"
    job.error_message = "Job was cancelled by the user."
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    await broker.publish(
        job.id,
        "error",
        ErrorEvent(
            job_id=str(job.id),
            code="cancelled",
            message="Job was cancelled by the user.",
            retryable=False,
        ).model_dump(mode="json"),
    )
    return job


async def list_jobs_for_experiment(session: AsyncSession, owner: User, experiment_id: UUID) -> list[Job]:
    await get_owned_experiment(session, owner, experiment_id)
    result = await session.execute(
        select(Job)
        .where(Job.experiment_id == experiment_id)
        .where(Job.owner_id == owner.id)
        .order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())
