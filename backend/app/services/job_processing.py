from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.schemas.run import RunExperimentRequest


TERMINAL_STATUSES = {JobStatus.complete, JobStatus.failed, JobStatus.cancelled}


class JobProcessingError(RuntimeError):
    pass


async def get_job_for_processing(session: AsyncSession, job_id: UUID) -> Job:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise JobProcessingError(f"Job {job_id} was not found")
    return job


async def mark_job_failed(
    session: AsyncSession,
    job: Job,
    *,
    error_code: str,
    error_message: str,
) -> Job:
    job.status = JobStatus.failed
    job.error_code = error_code
    job.error_message = error_message[:4000]
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    return job


async def process_fake_inference_job(session: AsyncSession, job_id: UUID) -> Job:
    job = await get_job_for_processing(session, job_id)

    if job.status in TERMINAL_STATUSES:
        return job

    try:
        RunExperimentRequest.model_validate(job.run_spec)
    except ValidationError as exc:
        return await mark_job_failed(
            session,
            job,
            error_code="validation_failed",
            error_message=str(exc),
        )

    started_at = datetime.now(UTC)
    job.status = JobStatus.running
    job.started_at = job.started_at or started_at
    job.error_code = None
    job.error_message = None
    await session.commit()
    await session.refresh(job)

    job.status = JobStatus.complete
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    return job
