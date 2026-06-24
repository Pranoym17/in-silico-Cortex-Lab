from dataclasses import dataclass, field
import hashlib
import json
import logging
from typing import Any
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import redis
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.ml import (
    OptimizerCandidate,
    OptimizerGenerationEvent,
    OptimizerRequest,
    OptimizerResult,
    OptimizerStartResponse,
)

logger = logging.getLogger(__name__)
ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"


@dataclass
class OptimizerJobRecord:
    id: UUID
    request: OptimizerRequest
    status: str = "queued"
    events: list[tuple[str, dict]] = field(default_factory=list)
    result: OptimizerResult | None = None


_OPTIMIZER_JOBS: dict[UUID, OptimizerJobRecord] = {}


def clear_optimizer_jobs() -> None:
    _OPTIMIZER_JOBS.clear()


def start_optimizer_job(request: OptimizerRequest) -> OptimizerStartResponse:
    job_id = uuid4()
    record = OptimizerJobRecord(id=job_id, request=request)
    _OPTIMIZER_JOBS[job_id] = record
    run_configured_optimizer(record)
    return OptimizerStartResponse(
        optimizer_job_id=job_id,
        status=record.status,
        stream_url=f"/api/ml/optimize/{job_id}/stream",
    )


def get_optimizer_job(job_id: UUID) -> OptimizerJobRecord | None:
    return _OPTIMIZER_JOBS.get(job_id)


def run_configured_optimizer(record: OptimizerJobRecord) -> None:
    provider = get_settings().optimizer_provider
    cached = get_cached_optimizer_result(record.request, provider)
    if cached is not None:
        replay_cached_result(record, cached)
        return

    if provider == "anthropic":
        run_anthropic_optimizer(record)
    else:
        run_fake_optimizer(record)

    if record.result is not None:
        set_cached_optimizer_result(record.request, provider, record.result)


def run_fake_optimizer(record: OptimizerJobRecord) -> None:
    request = record.request
    record.status = "running"
    record.events.append(
        (
            "queued",
            {
                "optimizer_job_id": str(record.id),
                "status": "queued",
                "target_region": request.target_region,
                "direction": request.direction,
            },
        )
    )

    best_score = float("-inf")
    best_stimulus = ""
    generations: list[OptimizerGenerationEvent] = []

    for generation in range(1, request.generations + 1):
        candidates = fake_candidates(request, generation)
        generation_best = max(candidates, key=lambda candidate: candidate.score)
        if generation_best.score > best_score:
            best_score = generation_best.score
            best_stimulus = generation_best.text

        event = OptimizerGenerationEvent(
            optimizer_job_id=record.id,
            generation=generation,
            best_score=best_score,
            best_stimulus=best_stimulus,
            candidates=candidates,
        )
        generations.append(event)
        record.events.append(("generation", event.model_dump(mode="json")))

    record.status = "complete"
    record.result = OptimizerResult(
        optimizer_job_id=record.id,
        status="complete",
        target_region=request.target_region,
        direction=request.direction,
        best_score=best_score,
        best_stimulus=best_stimulus,
        generations=generations,
    )
    record.events.append(("complete", record.result.model_dump(mode="json")))


def fake_candidates(request: OptimizerRequest, generation: int) -> list[OptimizerCandidate]:
    seed = request.seed_prompt.strip() if request.seed_prompt else "neuroscience stimulus"
    direction_word = "activate" if request.direction == "maximize" else "quiet"
    candidates: list[OptimizerCandidate] = []
    for index in range(request.candidates_per_generation):
        score_direction = 1 if request.direction == "maximize" else -1
        base_score = generation * 0.1 + index * 0.01
        score = score_direction * base_score
        candidates.append(
            OptimizerCandidate(
                text=f"{seed} crafted to {direction_word} {request.target_region} candidate {generation}-{index + 1}",
                score=score,
            )
        )
    return candidates


def run_anthropic_optimizer(record: OptimizerJobRecord) -> None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        fail_optimizer(record, "anthropic_api_key_missing", "ANTHROPIC_API_KEY is required when OPTIMIZER_PROVIDER=anthropic.")
        return

    request = record.request
    record.status = "running"
    record.events.append(
        (
            "queued",
            {
                "optimizer_job_id": str(record.id),
                "status": "queued",
                "target_region": request.target_region,
                "direction": request.direction,
            },
        )
    )

    best_score = float("-inf")
    best_stimulus = ""
    generations: list[OptimizerGenerationEvent] = []
    exemplars: list[str] = []
    for generation in range(1, request.generations + 1):
        try:
            texts = anthropic_candidate_texts(request, generation, exemplars)
        except Exception as exc:
            fail_optimizer(record, "anthropic_failed", f"Anthropic optimizer failed: {exc}")
            return
        candidates = [
            OptimizerCandidate(text=text, score=score_candidate(text, request, generation, index))
            for index, text in enumerate(texts[: request.candidates_per_generation])
        ]
        if not candidates:
            fail_optimizer(record, "anthropic_empty", "Anthropic returned no optimizer candidates.")
            return
        generation_best = max(candidates, key=lambda candidate: candidate.score)
        exemplars = [candidate.text for candidate in sorted(candidates, key=lambda item: item.score, reverse=True)[:5]]
        if generation_best.score > best_score:
            best_score = generation_best.score
            best_stimulus = generation_best.text
        event = OptimizerGenerationEvent(
            optimizer_job_id=record.id,
            generation=generation,
            best_score=best_score,
            best_stimulus=best_stimulus,
            candidates=candidates,
        )
        generations.append(event)
        record.events.append(("generation", event.model_dump(mode="json")))

    record.status = "complete"
    record.result = OptimizerResult(
        optimizer_job_id=record.id,
        status="complete",
        target_region=request.target_region,
        direction=request.direction,
        best_score=best_score,
        best_stimulus=best_stimulus,
        generations=generations,
    )
    record.events.append(("complete", record.result.model_dump(mode="json")))


def anthropic_candidate_texts(request: OptimizerRequest, generation: int, exemplars: list[str]) -> list[str]:
    seed = request.seed_prompt or "Generate concise text stimuli."
    exemplar_text = "\n".join(f"- {text}" for text in exemplars) if exemplars else "- none yet"
    prompt = (
        f"Target brain region: {request.target_region}\n"
        f"Direction: {request.direction}\n"
        f"Generation: {generation}\n"
        f"Seed prompt: {seed}\n"
        f"Strong prior candidates:\n{exemplar_text}\n\n"
        f"Return exactly {request.candidates_per_generation} candidate text stimuli as a JSON array of strings."
    )
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": prompt}],
    }
    response = _anthropic_request(payload)
    content = response.get("content")
    text = ""
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            text = str(first.get("text") or "")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
    return [item.strip() for item in parsed if isinstance(item, str) and item.strip()]


def _anthropic_request(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": settings.anthropic_api_key or "",
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def score_candidate(text: str, request: OptimizerRequest, generation: int, index: int) -> float:
    target_terms = [term for term in request.target_region.lower().replace("-", " ").split() if len(term) > 2]
    text_lower = text.lower()
    target_hits = sum(1 for term in target_terms if term in text_lower)
    length_bonus = min(len(text.split()) / 40.0, 1.0) * 0.05
    base = generation * 0.1 + index * 0.01 + target_hits * 0.08 + length_bonus
    return base if request.direction == "maximize" else -base


def fail_optimizer(record: OptimizerJobRecord, code: str, message: str) -> None:
    record.status = "failed"
    record.events.append(
        (
            "error",
            {
                "optimizer_job_id": str(record.id),
                "code": code,
                "message": message,
            },
        )
    )


def replay_cached_result(record: OptimizerJobRecord, cached: OptimizerResult) -> None:
    record.status = "complete"
    generations: list[OptimizerGenerationEvent] = []
    record.events.append(
        (
            "queued",
            {
                "optimizer_job_id": str(record.id),
                "status": "queued",
                "target_region": record.request.target_region,
                "direction": record.request.direction,
                "cache_hit": True,
            },
        )
    )
    for generation in cached.generations:
        event = OptimizerGenerationEvent(
            optimizer_job_id=record.id,
            generation=generation.generation,
            best_score=generation.best_score,
            best_stimulus=generation.best_stimulus,
            candidates=generation.candidates,
        )
        generations.append(event)
        record.events.append(("generation", event.model_dump(mode="json")))
    record.result = OptimizerResult(
        optimizer_job_id=record.id,
        status="complete",
        target_region=cached.target_region,
        direction=cached.direction,
        best_score=cached.best_score,
        best_stimulus=cached.best_stimulus,
        generations=generations,
    )
    record.events.append(("complete", record.result.model_dump(mode="json")))


def optimizer_cache_key(request: OptimizerRequest, provider: str) -> str:
    payload = json.dumps(
        {"request": request.model_dump(mode="json"), "provider": provider, "version": "optimizer-v1"},
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"cortex:ml:optimizer:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _redis_client():
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def get_cached_optimizer_result(request: OptimizerRequest, provider: str) -> OptimizerResult | None:
    settings = get_settings()
    if not settings.ml_cache_enabled:
        return None
    cache_key = optimizer_cache_key(request, provider)
    try:
        raw = _redis_client().get(cache_key)
    except Exception as exc:
        logger.warning("optimizer_cache_lookup_error", extra={"cache_key": cache_key}, exc_info=exc)
        return None
    if raw is None:
        return None
    try:
        return OptimizerResult.model_validate_json(raw)
    except (ValidationError, ValueError, TypeError):
        logger.warning("optimizer_cache_corrupt", extra={"cache_key": cache_key})
        return None


def set_cached_optimizer_result(request: OptimizerRequest, provider: str, result: OptimizerResult) -> None:
    settings = get_settings()
    if not settings.ml_cache_enabled:
        return
    cache_key = optimizer_cache_key(request, provider)
    try:
        _redis_client().setex(cache_key, settings.ml_cache_ttl_seconds, result.model_dump_json())
    except Exception as exc:
        logger.warning("optimizer_cache_write_error", extra={"cache_key": cache_key}, exc_info=exc)
