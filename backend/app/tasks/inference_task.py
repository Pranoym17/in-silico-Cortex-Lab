import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import create_worker_engine
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

    worker_engine = create_worker_engine()
    worker_sessions = async_sessionmaker(worker_engine, expire_on_commit=False)
    try:
        async with worker_sessions() as session:
            job = await process_configured_inference_job(session, parsed_job_id)
    finally:
        await worker_engine.dispose()

    status = job.status.value if isinstance(job.status, JobStatus) else str(job.status)
    return {"job_id": str(job.id), "status": status}
