from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus
from app.schemas.run import RunExperimentRequest
from app.schemas.sse import CompleteEvent, ErrorEvent, ProgressEvent, QueuedEvent, WarmingEvent
from app.services.activation_events import fake_activation_chunk
from app.services.sse_broker import JobEventBroker, get_job_event_broker


TERMINAL_STATUSES = {JobStatus.complete, JobStatus.failed, JobStatus.cancelled}
FAKE_VERTEX_COUNT = 16
FAKE_TIMESTEPS_PER_BLOCK = 1


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


async def process_fake_inference_job(
    session: AsyncSession,
    job_id: UUID,
    broker: JobEventBroker | None = None,
) -> Job:
    broker = broker or get_job_event_broker()
    job = await get_job_for_processing(session, job_id)

    if job.status in TERMINAL_STATUSES:
        return job

    await broker.publish(
        job.id,
        "queued",
        QueuedEvent(job_id=str(job.id), status=JobStatus.queued).model_dump(mode="json"),
    )

    try:
        run_request = RunExperimentRequest.model_validate(job.run_spec)
    except ValidationError as exc:
        failed_job = await mark_job_failed(
            session,
            job,
            error_code="validation_failed",
            error_message=str(exc),
        )
        await broker.publish(
            job.id,
            "error",
            ErrorEvent(
                job_id=str(job.id),
                code="validation_failed",
                message="Run specification failed validation.",
                retryable=False,
            ).model_dump(mode="json"),
        )
        return failed_job

    job.status = JobStatus.warming
    await session.commit()
    await session.refresh(job)
    await broker.publish(
        job.id,
        "warming",
        WarmingEvent(job_id=str(job.id), estimated_seconds=1).model_dump(mode="json"),
    )

    started_at = datetime.now(UTC)
    job.status = JobStatus.running
    job.started_at = job.started_at or started_at
    job.error_code = None
    job.error_message = None
    await session.commit()
    await session.refresh(job)

    total_blocks = len(run_request.blocks)
    completed_timesteps = 0
    await broker.publish(
        job.id,
        "progress",
        ProgressEvent(
            job_id=str(job.id),
            completed_blocks=0,
            total_blocks=total_blocks,
            completed_timesteps=completed_timesteps,
        ).model_dump(mode="json"),
    )

    sample_rate_hz = run_request.settings.target_sample_rate_hz
    for chunk_index, block in enumerate(run_request.blocks):
        chunk = fake_activation_chunk(
            job_id=str(job.id),
            block_id=block.id,
            chunk_index=chunk_index,
            timestep_start=completed_timesteps,
            timestep_count=FAKE_TIMESTEPS_PER_BLOCK,
            vertex_count=FAKE_VERTEX_COUNT,
            sample_rate_hz=sample_rate_hz,
        )
        await broker.publish(job.id, "chunk", chunk.model_dump(mode="json"))

        completed_timesteps += FAKE_TIMESTEPS_PER_BLOCK
        await broker.publish(
            job.id,
            "progress",
            ProgressEvent(
                job_id=str(job.id),
                completed_blocks=chunk_index + 1,
                total_blocks=total_blocks,
                completed_timesteps=completed_timesteps,
            ).model_dump(mode="json"),
        )

    job.status = JobStatus.complete
    job.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(job)
    await broker.publish(
        job.id,
        "complete",
        CompleteEvent(
            job_id=str(job.id),
            status=JobStatus.complete,
            timesteps=completed_timesteps,
            vertex_count=FAKE_VERTEX_COUNT,
        ).model_dump(mode="json"),
    )
    return job
