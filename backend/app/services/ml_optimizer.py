from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.schemas.ml import (
    OptimizerCandidate,
    OptimizerGenerationEvent,
    OptimizerRequest,
    OptimizerResult,
    OptimizerStartResponse,
)


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
    run_fake_optimizer(record)
    return OptimizerStartResponse(
        optimizer_job_id=job_id,
        status=record.status,
        stream_url=f"/api/ml/optimize/{job_id}/stream",
    )


def get_optimizer_job(job_id: UUID) -> OptimizerJobRecord | None:
    return _OPTIMIZER_JOBS.get(job_id)


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
