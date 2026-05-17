from fastapi import APIRouter, Depends, status

from app.api.dependencies import require_user
from app.models.user import User
from app.schemas.run import RunExperimentRequest, RunExperimentResponse

router = APIRouter()


@router.post("/{experiment_id}/run", response_model=RunExperimentResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_experiment(
    experiment_id: str,
    body: RunExperimentRequest,
    user: User = Depends(require_user),
) -> RunExperimentResponse:
    job_id = f"job_local_{experiment_id}"
    # Persistence and Celery enqueueing will be wired after the database layer lands.
    return RunExperimentResponse(
        job_id=job_id,
        experiment_id=experiment_id,
        status="queued",
        stream_url=f"/api/jobs/{job_id}/stream",
        user_id=str(user.id),
    )
