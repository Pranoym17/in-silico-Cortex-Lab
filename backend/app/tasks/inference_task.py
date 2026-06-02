import asyncio
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.models.job import JobStatus
from app.services.job_processing import JobProcessingError, process_configured_inference_job
from app.tasks.celery_app import celery_app


@celery_app.task(name="run_inference")
def run_inference(job_id: str) -> dict[str, str]:
    return asyncio.run(_run_inference(job_id))


async def _run_inference(job_id: str) -> dict[str, str]:
    try:
        parsed_job_id = UUID(job_id)
    except ValueError as exc:
        raise JobProcessingError(f"Invalid job id: {job_id}") from exc

    async with AsyncSessionLocal() as session:
        job = await process_configured_inference_job(session, parsed_job_id)

    status = job.status.value if isinstance(job.status, JobStatus) else str(job.status)
    return {"job_id": str(job.id), "status": status}
