from fastapi import APIRouter, Request, status

from app.schemas.run import RunExperimentRequest, RunExperimentResponse

router = APIRouter()


@router.post("/{experiment_id}/run", response_model=RunExperimentResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_experiment(experiment_id: str, body: RunExperimentRequest, request: Request) -> RunExperimentResponse:
    user = getattr(request.state, "user", None)
    job_id = f"job_local_{experiment_id}"
    # Persistence and Celery enqueueing will be wired after the database layer lands.
    return RunExperimentResponse(
        job_id=job_id,
        experiment_id=experiment_id,
        status="queued",
        stream_url=f"/api/jobs/{job_id}/stream",
        user_id=user["id"] if user else None,
    )

