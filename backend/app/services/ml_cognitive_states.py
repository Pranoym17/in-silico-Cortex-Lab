from typing import Any
from uuid import UUID

import numpy as np
from fastapi import HTTPException, status
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.ml import CognitiveStatePoint, CognitiveStatesResponse
from app.services.jobs import get_owned_job
from app.services.ml_results import load_owned_result_matrix
from app.services.ml_rsa import block_timestep_ranges


COGNITIVE_STATE_LABELS = [
    "Visual - Objects",
    "Visual - Scenes",
    "Face Processing",
    "Language Comprehension",
    "Auditory - Speech",
    "Auditory - Music",
    "Reading",
    "Rest / Low Activation",
]
CLASSIFIER_VERSION = "rules-v1"


def score_from_activation(frame: NDArray[np.float32]) -> float:
    mean_abs = float(np.mean(np.abs(frame))) if frame.size else 0.0
    return max(0.0, min(1.0, mean_abs / 2.0))


def block_for_timestep(run_spec: dict[str, Any], timestep: int, timestep_count: int, sample_rate_hz: float | None) -> dict[str, Any] | None:
    blocks = run_spec.get("blocks")
    if not isinstance(blocks, list):
        return None
    ranges = block_timestep_ranges(run_spec, timestep_count, sample_rate_hz)
    for block, (start, end) in zip(blocks, ranges, strict=False):
        if start <= timestep < end and isinstance(block, dict):
            return block
    return None


def label_for_block(block: dict[str, Any] | None, activation_score: float) -> str:
    if activation_score < 0.04:
        return "Rest / Low Activation"
    if not block:
        return "Rest / Low Activation"

    condition = str(block.get("condition") or "").lower()
    block_type = str(block.get("type") or "").lower()
    text = str(block.get("text") or "").lower()
    joined = " ".join([condition, block_type, text])

    if any(token in joined for token in ("face", "ffa", "fusiform")):
        return "Face Processing"
    if any(token in joined for token in ("scene", "house", "place", "landscape", "room")):
        return "Visual - Scenes"
    if any(token in joined for token in ("music", "song", "melody", "instrument")):
        return "Auditory - Music"
    if any(token in joined for token in ("speech", "spoken", "voice", "podcast")):
        return "Auditory - Speech"
    if any(token in joined for token in ("read", "word", "sentence", "language", "story", "text")):
        return "Language Comprehension"
    if block_type == "audio":
        return "Auditory - Speech"
    if block_type == "text":
        return "Language Comprehension"
    if block_type == "image":
        return "Visual - Objects"
    return "Rest / Low Activation"


def scores_for_label(label: str, confidence: float) -> dict[str, float]:
    baseline = (1.0 - confidence) / (len(COGNITIVE_STATE_LABELS) - 1)
    scores = {state_label: baseline for state_label in COGNITIVE_STATE_LABELS}
    scores[label] = confidence
    return scores


def classify_cognitive_states(
    job_id: UUID,
    run_spec: dict[str, Any],
    activations: NDArray[np.float32],
    sample_rate_hz: float | None,
) -> CognitiveStatesResponse:
    if activations.ndim != 2:
        raise ValueError("Cognitive state classification requires a 2D activation matrix")

    states: list[CognitiveStatePoint] = []
    timestep_count = int(activations.shape[0])
    for timestep in range(timestep_count):
        frame = activations[timestep]
        activation_score = score_from_activation(frame)
        block = block_for_timestep(run_spec, timestep, timestep_count, sample_rate_hz)
        label = label_for_block(block, activation_score)
        confidence = 0.35 + activation_score * 0.5
        if label == "Rest / Low Activation":
            confidence = max(0.55, 1.0 - activation_score)
        confidence = max(0.0, min(1.0, confidence))
        states.append(
            CognitiveStatePoint(
                timestep=timestep,
                label=label,
                confidence=confidence,
                scores=scores_for_label(label, confidence),
            )
        )

    return CognitiveStatesResponse(job_id=job_id, classifier_version=CLASSIFIER_VERSION, states=states)


async def get_cognitive_states(session: AsyncSession, owner: User, job_id: UUID) -> CognitiveStatesResponse:
    job = await get_owned_job(session, owner, job_id)
    result_matrix = await load_owned_result_matrix(session, owner, job_id)
    try:
        return classify_cognitive_states(
            job_id,
            job.run_spec,
            result_matrix.activations,
            result_matrix.result.sample_rate_hz,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
