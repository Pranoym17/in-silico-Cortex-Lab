from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

from app.services import ml_results
from app.services.ml_results import MlResultLoadError, parse_activation_npz


def make_result(**overrides):
    matrix = overrides.pop("matrix", np.array([[1.0, 2.0], [3.0, 4.0]], dtype="<f4"))
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "job_id": uuid4(),
        "experiment_id": uuid4(),
        "owner_id": uuid4(),
        "s3_key": "results/job-1/activations.npz",
        "shape": list(matrix.shape),
        "vertex_count": int(matrix.shape[1]),
        "timestep_count": int(matrix.shape[0]),
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return SimpleNamespace(**data), matrix


def npz_payload(matrix: np.ndarray) -> bytes:
    buffer = BytesIO()
    np.savez_compressed(buffer, activations=np.ascontiguousarray(matrix, dtype="<f4"))
    return buffer.getvalue()


def test_parse_activation_npz_returns_float32_matrix():
    result, matrix = make_result()

    parsed = parse_activation_npz(npz_payload(matrix), result)

    assert parsed.dtype == np.dtype("float32")
    assert parsed.tolist() == [[1.0, 2.0], [3.0, 4.0]]


def test_parse_activation_npz_rejects_shape_mismatch():
    result, matrix = make_result(shape=[1, 4])

    with pytest.raises(MlResultLoadError, match="shape does not match metadata"):
        parse_activation_npz(npz_payload(matrix), result)


def test_parse_activation_npz_rejects_missing_activations():
    result, _matrix = make_result()
    buffer = BytesIO()
    np.savez_compressed(buffer, not_activations=np.array([1.0], dtype="<f4"))

    with pytest.raises(MlResultLoadError, match="missing activations"):
        parse_activation_npz(buffer.getvalue(), result)


def test_download_result_npz_reads_s3_object(monkeypatch):
    class FakeBody:
        def read(self):
            return b"npz-bytes"

    class FakeS3Client:
        def get_object(self, **kwargs):
            assert kwargs == {"Bucket": "cortexlab-results", "Key": "results/job-1/activations.npz"}
            return {"Body": FakeBody()}

    monkeypatch.setattr(ml_results, "_s3_client", lambda: FakeS3Client())
    ml_results.get_settings.cache_clear()
    monkeypatch.setenv("S3_BUCKET_NAME", "cortexlab-results")

    assert ml_results.download_result_npz("results/job-1/activations.npz") == b"npz-bytes"
    ml_results.get_settings.cache_clear()
