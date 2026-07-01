from dataclasses import dataclass
from typing import Any

import numpy as np
from fastapi import HTTPException, status
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.ml import MdsPoint, RsaRequest, RsaResponse
from app.services.jobs import get_owned_job
from app.services.ml_results import load_owned_result_matrix


@dataclass(frozen=True)
class BlockActivationSet:
    labels: list[str]
    vectors: NDArray[np.float32]


def block_labels_from_run_spec(run_spec: dict[str, Any]) -> list[str]:
    blocks = run_spec.get("blocks")
    if not isinstance(blocks, list):
        return []

    labels: list[str] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            labels.append(f"Block {index + 1}")
            continue
        condition = block.get("condition")
        if isinstance(condition, str) and condition.strip():
            labels.append(condition.strip())
            continue
        block_type = block.get("type")
        if isinstance(block_type, str) and block_type.strip():
            labels.append(f"{block_type.title()} {index + 1}")
            continue
        labels.append(f"Block {index + 1}")
    return labels


def block_timestep_ranges(
    run_spec: dict[str, Any],
    timestep_count: int,
    sample_rate_hz: float | None,
    result_metadata: dict[str, Any] | None = None,
) -> list[tuple[int, int]]:
    blocks = run_spec.get("blocks")
    if not isinstance(blocks, list) or not blocks or timestep_count <= 0:
        return []

    mapped_ranges = output_timestep_ranges(blocks, timestep_count, result_metadata)
    if mapped_ranges:
        return mapped_ranges

    sample_rate = sample_rate_hz if sample_rate_hz and sample_rate_hz > 0 else 2.0
    ranges: list[tuple[int, int]] = []
    timeline_valid = True

    for block in blocks:
        if not isinstance(block, dict):
            timeline_valid = False
            break
        start_ms = block.get("start_ms")
        duration_ms = block.get("duration_ms")
        if not isinstance(start_ms, int) or not isinstance(duration_ms, int) or duration_ms <= 0:
            timeline_valid = False
            break
        start = int(round((start_ms / 1000.0) * sample_rate))
        end = start + max(1, int(round((duration_ms / 1000.0) * sample_rate)))
        if start >= timestep_count:
            timeline_valid = False
            break
        ranges.append((max(0, start), min(timestep_count, end)))

    if timeline_valid and ranges and all(start < end for start, end in ranges):
        final_start, final_end = ranges[-1]
        if final_end < timestep_count:
            ranges[-1] = (final_start, timestep_count)
        return ranges

    return even_timestep_ranges(len(blocks), timestep_count)


def output_timestep_ranges(
    blocks: list[Any],
    timestep_count: int,
    result_metadata: dict[str, Any] | None,
) -> list[tuple[int, int]]:
    if not isinstance(result_metadata, dict):
        return []
    stimuli = result_metadata.get("stimuli")
    if not isinstance(stimuli, list):
        return []
    by_id = {
        str(item.get("block_id")): item
        for item in stimuli
        if isinstance(item, dict) and item.get("block_id")
    }
    ranges: list[tuple[int, int]] = []
    for block in blocks:
        if not isinstance(block, dict) or str(block.get("id")) not in by_id:
            return []
        timing = by_id[str(block.get("id"))]
        start = timing.get("output_timestep_start")
        count = timing.get("output_timestep_count")
        if not isinstance(start, int) or not isinstance(count, int) or start < 0 or count <= 0:
            return []
        end = start + count
        if end > timestep_count:
            return []
        ranges.append((start, end))
    return ranges


def even_timestep_ranges(block_count: int, timestep_count: int) -> list[tuple[int, int]]:
    if block_count <= 0 or timestep_count <= 0:
        return []

    boundaries = np.linspace(0, timestep_count, block_count + 1)
    ranges: list[tuple[int, int]] = []
    for index in range(block_count):
        start = int(round(float(boundaries[index])))
        end = int(round(float(boundaries[index + 1])))
        if start == end:
            end = min(timestep_count, start + 1)
        ranges.append((start, end))
    return ranges


def aggregate_block_vectors(
    activations: NDArray[np.float32],
    run_spec: dict[str, Any],
    sample_rate_hz: float | None,
    result_metadata: dict[str, Any] | None = None,
) -> BlockActivationSet:
    labels = block_labels_from_run_spec(run_spec)
    ranges = block_timestep_ranges(run_spec, int(activations.shape[0]), sample_rate_hz, result_metadata)
    if len(labels) != len(ranges):
        raise ValueError("Run specification does not describe block timing")
    if len(ranges) < 2:
        raise ValueError("RSA requires at least two stimulus blocks per job")

    vectors = []
    for start, end in ranges:
        if start >= end:
            raise ValueError("Block timestep range is empty")
        vectors.append(np.mean(activations[start:end], axis=0))

    return BlockActivationSet(labels=labels, vectors=np.ascontiguousarray(np.vstack(vectors), dtype="<f4"))


def cosine_dissimilarity_matrix(vectors: NDArray[np.float32]) -> NDArray[np.float64]:
    matrix = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    safe_norms = np.where(norms == 0, 1.0, norms)
    normalized = matrix / safe_norms[:, None]
    similarity = normalized @ normalized.T
    dissimilarity = 1.0 - np.clip(similarity, -1.0, 1.0)
    np.fill_diagonal(dissimilarity, 0.0)
    return dissimilarity


def upper_triangle_values(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    if matrix.shape[0] < 2:
        return np.array([], dtype=np.float64)
    indices = np.triu_indices(matrix.shape[0], k=1)
    return matrix[indices]


def rank_values(values: NDArray[np.float64]) -> NDArray[np.float64]:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    sorted_values = values[order]
    index = 0
    while index < len(values):
        end = index + 1
        while end < len(values) and sorted_values[end] == sorted_values[index]:
            end += 1
        average_rank = (index + end - 1) / 2.0 + 1.0
        ranks[order[index:end]] = average_rank
        index = end
    return ranks


def spearman_correlation(values_a: NDArray[np.float64], values_b: NDArray[np.float64]) -> float:
    if values_a.shape != values_b.shape or len(values_a) == 0:
        raise ValueError("RSA inputs must have matching non-empty upper triangles")

    ranks_a = rank_values(values_a)
    ranks_b = rank_values(values_b)
    centered_a = ranks_a - np.mean(ranks_a)
    centered_b = ranks_b - np.mean(ranks_b)
    denominator = float(np.linalg.norm(centered_a) * np.linalg.norm(centered_b))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(centered_a, centered_b) / denominator)


def classical_mds(rdm: NDArray[np.float64], labels: list[str]) -> list[MdsPoint]:
    count = rdm.shape[0]
    if count == 0:
        return []

    squared = rdm**2
    centering = np.eye(count) - np.ones((count, count)) / count
    gram = -0.5 * centering @ squared @ centering
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    order = np.argsort(eigenvalues)[::-1]
    coords = np.zeros((count, 2), dtype=np.float64)

    for output_dim, eigen_index in enumerate(order[:2]):
        eigenvalue = max(float(eigenvalues[eigen_index]), 0.0)
        coords[:, output_dim] = eigenvectors[:, eigen_index] * np.sqrt(eigenvalue)

    return [
        MdsPoint(x=float(coords[index, 0]), y=float(coords[index, 1]), label=labels[index], index=index)
        for index in range(count)
    ]


def compute_rsa_response(
    request: RsaRequest,
    run_spec_a: dict[str, Any],
    activations_a: NDArray[np.float32],
    sample_rate_hz_a: float | None,
    run_spec_b: dict[str, Any],
    activations_b: NDArray[np.float32],
    sample_rate_hz_b: float | None,
    result_metadata_a: dict[str, Any] | None = None,
    result_metadata_b: dict[str, Any] | None = None,
) -> RsaResponse:
    if activations_a.shape[1] != activations_b.shape[1]:
        raise ValueError("RSA requires both jobs to have the same vertex count")

    set_a = aggregate_block_vectors(activations_a, run_spec_a, sample_rate_hz_a, result_metadata_a)
    set_b = aggregate_block_vectors(activations_b, run_spec_b, sample_rate_hz_b, result_metadata_b)
    if set_a.vectors.shape[0] != set_b.vectors.shape[0]:
        raise ValueError("RSA requires both jobs to have the same number of stimulus blocks")

    rdm_a = cosine_dissimilarity_matrix(set_a.vectors)
    rdm_b = cosine_dissimilarity_matrix(set_b.vectors)
    rsa_score = max(-1.0, min(1.0, spearman_correlation(upper_triangle_values(rdm_a), upper_triangle_values(rdm_b))))

    return RsaResponse(
        job_id_a=request.job_id_a,
        job_id_b=request.job_id_b,
        rsa_score=rsa_score,
        rdm_a=rdm_a.tolist(),
        rdm_b=rdm_b.tolist(),
        labels_a=set_a.labels,
        labels_b=set_b.labels,
        mds_a=classical_mds(rdm_a, set_a.labels),
        mds_b=classical_mds(rdm_b, set_b.labels),
        block_count=int(set_a.vectors.shape[0]),
        vertex_count=int(activations_a.shape[1]),
    )


async def run_rsa(session: AsyncSession, owner: User, request: RsaRequest) -> RsaResponse:
    job_a = await get_owned_job(session, owner, request.job_id_a)
    job_b = await get_owned_job(session, owner, request.job_id_b)
    result_a = await load_owned_result_matrix(session, owner, request.job_id_a)
    result_b = await load_owned_result_matrix(session, owner, request.job_id_b)

    try:
        return compute_rsa_response(
            request,
            job_a.run_spec,
            result_a.activations,
            result_a.result.sample_rate_hz,
            job_b.run_spec,
            result_b.activations,
            result_b.result.sample_rate_hz,
            result_a.result.metadata_json,
            result_b.result.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
