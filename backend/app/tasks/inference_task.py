import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.database import create_worker_engine
from app.models.job import JobStatus
from app.services.error_codes import is_retryable_job_error
from app.services.job_processing import (
    JobProcessingError,
    process_configured_inference_job,
    requeue_retryable_failed_job,
)
from app.tasks.celery_app import celery_app


def retry_delay_seconds(retry_number: int, base_seconds: int) -> int:
    """Use bounded exponential backoff for transient infrastructure failures."""
    return min(base_seconds * (2**retry_number), 15 * 60)


@celery_app.task(bind=True, name="run_inference")
def run_inference(self, job_id: str) -> dict[str, str | bool]:
    settings = get_settings()
    result = asyncio.run(_run_inference(job_id, retrying=self.request.retries > 0))
    if (
        result["status"] == JobStatus.failed.value
        and result["retryable"]
        and self.request.retries < settings.celery_task_max_retries
    ):
        raise self.retry(
            countdown=retry_delay_seconds(self.request.retries, settings.celery_task_retry_backoff_seconds),
            max_retries=settings.celery_task_max_retries,
        )
    return result


async def _run_inference(job_id: str, *, retrying: bool = False) -> dict[str, str | bool]:
    try:
        parsed_job_id = UUID(job_id)
    except ValueError as exc:
        raise JobProcessingError(f"Invalid job id: {job_id}") from exc

    worker_engine = create_worker_engine()
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    try:
        async with worker_sessions() as session:
            if retrying:
                await requeue_retryable_failed_job(session, parsed_job_id)
            job = await process_configured_inference_job(session, parsed_job_id)
    finally:
        await worker_engine.dispose()

    status = job.status.value if isinstance(job.status, JobStatus) else str(job.status)
    return {
        "job_id": str(job.id),
        "status": status,
        "retryable": status == JobStatus.failed.value and is_retryable_job_error(job.error_code),
    }
