from uuid import uuid4

import numpy as np
import pytest

from app.schemas.ml import RsaRequest
from app.services.ml_rsa import (
    aggregate_block_vectors,
    block_timestep_ranges,
    classical_mds,
    compute_rsa_response,
    cosine_dissimilarity_matrix,
    spearman_correlation,
)


def run_spec(labels=("faces", "houses", "words")):
    return {
        "blocks": [
            {"id": f"block-{index}", "type": "text", "condition": label, "start_ms": index * 1000, "duration_ms": 1000}
            for index, label in enumerate(labels)
        ],
        "settings": {"target_sample_rate_hz": 1, "surface": "fsaverage5"},
    }


def test_block_timestep_ranges_falls_back_to_even_split_when_timeline_exceeds_matrix():
    spec = {
        "blocks": [
            {"start_ms": 0, "duration_ms": 5000},
            {"start_ms": 5000, "duration_ms": 5000},
        ]
    }

    assert block_timestep_ranges(spec, timestep_count=2, sample_rate_hz=2) == [(0, 1), (1, 2)]


def test_aggregate_block_vectors_means_each_block_range():
    activations = np.array([[1.0, 3.0], [5.0, 7.0], [10.0, 20.0]], dtype="<f4")

    block_set = aggregate_block_vectors(activations, run_spec(("a", "b")), sample_rate_hz=1)

    assert block_set.labels == ["a", "b"]
    assert block_set.vectors.tolist() == [[1.0, 3.0], [7.5, 13.5]]


def test_cosine_dissimilarity_matrix_sets_diagonal_to_zero():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="<f4")

    rdm = cosine_dissimilarity_matrix(vectors)

    assert rdm.tolist() == [[0.0, 1.0], [1.0, 0.0]]


def test_spearman_correlation_handles_ranked_vectors():
    assert spearman_correlation(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0])) == pytest.approx(1.0)
    assert spearman_correlation(np.array([1.0, 2.0, 3.0]), np.array([3.0, 2.0, 1.0])) == pytest.approx(-1.0)


def test_classical_mds_returns_one_point_per_label():
    rdm = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float64)

    points = classical_mds(rdm, ["a", "b"])

    assert [point.label for point in points] == ["a", "b"]
    assert len(points) == 2


def test_compute_rsa_response_compares_two_jobs():
    request = RsaRequest(job_id_a=uuid4(), job_id_b=uuid4())
    activations_a = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype="<f4")
    activations_b = np.array([[2.0, 0.0], [0.0, 2.0], [2.0, 2.0]], dtype="<f4")

    response = compute_rsa_response(
        request,
        run_spec(),
        activations_a,
        1,
        run_spec(),
        activations_b,
        1,
    )

    assert response.rsa_score == pytest.approx(1.0)
    assert response.labels_a == ["faces", "houses", "words"]
    assert response.labels_b == ["faces", "houses", "words"]
    assert response.block_count == 3
    assert response.vertex_count == 2
    assert len(response.rdm_a) == 3


def test_compute_rsa_response_rejects_block_count_mismatch():
    request = RsaRequest(job_id_a=uuid4(), job_id_b=uuid4())

    with pytest.raises(ValueError, match="same number of stimulus blocks"):
        compute_rsa_response(
            request,
            run_spec(("a", "b")),
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype="<f4"),
            1,
            run_spec(("a", "b", "c")),
            np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]], dtype="<f4"),
            1,
        )
