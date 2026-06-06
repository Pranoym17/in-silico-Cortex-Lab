from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

from app.services import result_storage
from app.services.result_storage import ActivationMatrixAssembler, ResultStorageError, store_job_result


def chunk_event(timestep_start: int, values: list[list[float]]) -> dict:
    matrix = np.array(values, dtype="<f4")
    timestep_count, vertex_count = matrix.shape
    return {
        "type": "chunk",
        "job_id": "job-1",
        "block_id": "block-1",
        "chunk_index": timestep_start,
        "timestep_start": timestep_start,
        "timestep_count": timestep_count,
        "sample_rate_hz": 2,
        "vertex_count": vertex_count,
        "dtype": "float32",
        "shape": [timestep_count, vertex_count],
        "activations": matrix.tobytes(order="C"),
    }


def test_activation_matrix_assembler_orders_chunks():
    assembler = ActivationMatrixAssembler()

    assembler.add_chunk(chunk_event(1, [[3.0, 4.0]]))
    assembler.add_chunk(chunk_event(0, [[1.0, 2.0]]))

    matrix = assembler.assemble()

    assert matrix.dtype == np.dtype("float32")
    assert matrix.tolist() == [[1.0, 2.0], [3.0, 4.0]]
    assert assembler.vertex_count == 2
    assert assembler.sample_rate_hz == 2.0


def test_activation_matrix_assembler_rejects_missing_timesteps():
    assembler = ActivationMatrixAssembler()
    assembler.add_chunk(chunk_event(1, [[3.0, 4.0]]))

    with pytest.raises(ResultStorageError, match="missing timesteps"):
        assembler.assemble()


@pytest.mark.asyncio
async def test_store_job_result_writes_npz_and_result_row(monkeypatch):
    captured_put = {}

    class FakeS3Client:
        def put_object(self, **kwargs):
            captured_put.update(kwargs)

    monkeypatch.setattr(result_storage, "_s3_client", lambda: FakeS3Client())
    result_storage.get_settings.cache_clear()
    monkeypatch.setenv("S3_BUCKET_NAME", "cortexlab-results")
    monkeypatch.setenv("RESULTS_S3_PREFIX", "results")

    added = []

    class FakeSession:
        def add(self, value):
            added.append(value)

        async def flush(self):
            return None

    job = SimpleNamespace(id=uuid4(), experiment_id=uuid4(), owner_id=uuid4())
    matrix = np.array([[1.0, 2.0], [3.0, 4.0]], dtype="<f4")

    result = await store_job_result(
        FakeSession(),
        job,
        matrix,
        sample_rate_hz=2.0,
        model_version="test",
        metadata={"surface": "fsaverage5"},
    )

    assert captured_put["Bucket"] == "cortexlab-results"
    assert captured_put["Key"] == f"results/{job.id}/activations.npz"
    assert captured_put["ContentType"] == "application/octet-stream"
    assert isinstance(captured_put["Body"], bytes)
    assert added == [result]
    assert result.s3_key == f"results/{job.id}/activations.npz"
    assert result.shape == [2, 2]
    assert result.vertex_count == 2
    assert result.timestep_count == 2
    assert result.sample_rate_hz == 2.0
    assert result.model_name == "tribev2"
    assert result.model_version == "test"
    assert result.metadata_json == {"surface": "fsaverage5"}
    result_storage.get_settings.cache_clear()
