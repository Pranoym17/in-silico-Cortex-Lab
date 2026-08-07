from uuid import UUID

from app.services.ml_optimizer import get_optimizer_job, run_configured_optimizer
from app.tasks.celery_app import celery_app


@celery_app.task(name="run_optimizer")
def run_optimizer(job_id: str) -> dict[str, str]:
    record = get_optimizer_job(UUID(job_id))
    if record is None:
        raise ValueError(f"Optimizer job {job_id} was not found")
    run_configured_optimizer(record)
    return {"optimizer_job_id": str(record.id), "status": record.status}
