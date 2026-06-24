from uuid import UUID

from app.schemas.ml import OptimizerRequest
from app.services import ml_optimizer
from app.services.ml_optimizer import (
    anthropic_candidate_texts,
    clear_optimizer_jobs,
    fake_candidates,
    get_optimizer_job,
    optimizer_cache_key,
    start_optimizer_job,
)


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


def test_optimizer_cache_key_is_stable():
    request = OptimizerRequest(target_region="Left Fusiform", direction="maximize")

    assert optimizer_cache_key(request, "fake") == optimizer_cache_key(request, "fake")
    assert optimizer_cache_key(request, "fake") != optimizer_cache_key(request, "anthropic")


def test_cached_optimizer_result_is_replayed_with_new_job_id(monkeypatch):
    request = OptimizerRequest(target_region="Left Fusiform", direction="maximize", generations=1, candidates_per_generation=1)
    first = start_optimizer_job(request)
    cached = get_optimizer_job(first.optimizer_job_id).result
    clear_optimizer_jobs()

    monkeypatch.setattr(ml_optimizer, "get_cached_optimizer_result", lambda request, provider: cached)
    response = start_optimizer_job(request)
    record = get_optimizer_job(response.optimizer_job_id)

    assert record.result.optimizer_job_id == response.optimizer_job_id
    assert record.events[0][1]["cache_hit"] is True


def test_anthropic_provider_fails_without_api_key(monkeypatch):
    ml_optimizer.get_settings.cache_clear()
    monkeypatch.setenv("OPTIMIZER_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    response = start_optimizer_job(OptimizerRequest(target_region="Left Fusiform", direction="maximize"))
    record = get_optimizer_job(response.optimizer_job_id)

    assert response.status == "failed"
    assert record.events[-1][0] == "error"
    assert record.events[-1][1]["code"] == "anthropic_api_key_missing"
    ml_optimizer.get_settings.cache_clear()


def test_anthropic_candidate_texts_parses_json_array(monkeypatch):
    ml_optimizer.get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    monkeypatch.setattr(
        ml_optimizer,
        "_anthropic_request",
        lambda payload: {"content": [{"type": "text", "text": '["face sentence", "object sentence"]'}]},
    )

    candidates = anthropic_candidate_texts(
        OptimizerRequest(target_region="Left Fusiform", direction="maximize", candidates_per_generation=2),
        generation=1,
        exemplars=[],
    )

    assert candidates == ["face sentence", "object sentence"]
    ml_optimizer.get_settings.cache_clear()
