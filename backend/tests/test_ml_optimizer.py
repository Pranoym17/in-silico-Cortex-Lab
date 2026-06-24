from uuid import UUID

from app.schemas.ml import OptimizerRequest
from app.services.ml_optimizer import clear_optimizer_jobs, fake_candidates, get_optimizer_job, start_optimizer_job


def setup_function():
    clear_optimizer_jobs()


def test_fake_candidates_are_deterministic():
    request = OptimizerRequest(target_region="Left Fusiform", direction="maximize", generations=2, candidates_per_generation=2)

    candidates = fake_candidates(request, generation=2)

    assert [candidate.score for candidate in candidates] == [0.2, 0.21000000000000002]
    assert "Left Fusiform" in candidates[0].text


def test_start_optimizer_job_records_generation_and_complete_events():
    response = start_optimizer_job(
        OptimizerRequest(target_region="Left Fusiform", direction="maximize", generations=2, candidates_per_generation=2)
    )

    record = get_optimizer_job(response.optimizer_job_id)

    assert isinstance(response.optimizer_job_id, UUID)
    assert response.status == "complete"
    assert response.stream_url == f"/api/ml/optimize/{response.optimizer_job_id}/stream"
    assert record is not None
    assert [event for event, _data in record.events] == ["queued", "generation", "generation", "complete"]
    assert record.result is not None
    assert record.result.best_score == 0.21000000000000002
