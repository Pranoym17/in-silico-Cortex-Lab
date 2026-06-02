import logging
from uuid import UUID

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.job_processing import JobProcessingError, process_configured_inference_job

logger = logging.getLogger(__name__)


async def process_job_in_background(job_id: UUID) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await process_configured_inference_job(session, job_id)
    except JobProcessingError:
        logger.exception("Job processing failed before a job row could be updated", extra={"job_id": str(job_id)})
    except Exception:
        logger.exception("Unexpected background job processing failure", extra={"job_id": str(job_id)})


def dispatch_inference_job(background_tasks: BackgroundTasks, job_id: UUID) -> None:
    settings = get_settings()

    if settings.job_execution_mode == "background":
        background_tasks.add_task(process_job_in_background, job_id)
        return

    if settings.job_execution_mode == "celery":
        from app.tasks.inference_task import run_inference

        run_inference.delay(str(job_id))
        return

    if settings.job_execution_mode == "manual":
        return

    raise ValueError(f"Unsupported job execution mode: {settings.job_execution_mode}")
