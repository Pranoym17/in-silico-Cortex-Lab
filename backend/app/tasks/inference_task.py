from app.tasks.celery_app import celery_app


@celery_app.task(name="run_inference")
def run_inference(job_id: str) -> dict[str, str]:
    # Modal remote_gen streaming is wired after credentials and TRIBE v2 are available.
    return {"job_id": job_id, "status": "queued"}

