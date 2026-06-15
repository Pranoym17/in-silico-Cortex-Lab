from io import BytesIO
import logging
import time
from typing import Any

import boto3
import numpy as np
from botocore.exceptions import ClientError
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.job import Job
from app.models.result import Result

logger = logging.getLogger(__name__)


class ResultStorageError(RuntimeError):
    pass


def _s3_client():
    settings = get_settings()
    client_kwargs = {
        "region_name": settings.aws_region,
        "endpoint_url": f"https://s3.{settings.aws_region}.amazonaws.com",
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **client_kwargs)


def result_object_key(job_id: str) -> str:
    settings = get_settings()
    prefix = settings.results_s3_prefix.strip("/").strip()
    return f"{prefix}/{job_id}/activations.npz" if prefix else f"{job_id}/activations.npz"


def create_result_download_url(s3_key: str) -> str:
    settings = get_settings()
    return _s3_client().generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": s3_key,
        },
        ExpiresIn=settings.result_download_expires_seconds,
        HttpMethod="GET",
    )


def result_artifact_exists(s3_key: str) -> bool:
    try:
        _s3_client().head_object(Bucket=get_settings().s3_bucket_name, Key=s3_key)
        return True
    except ClientError as exc:
        status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        error_code = exc.response.get("Error", {}).get("Code")
        if status_code == 404 or error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise ResultStorageError(f"Failed to check result artifact: {exc}") from exc
    except Exception as exc:
        raise ResultStorageError(f"Failed to check result artifact: {exc}") from exc


class ActivationMatrixAssembler:
    def __init__(self) -> None:
        self._chunks: list[tuple[int, NDArray[np.float32]]] = []
        self.vertex_count: int | None = None
        self.sample_rate_hz: float | None = None

    def add_chunk(self, event: dict[str, Any]) -> None:
        vertex_count = int(event["vertex_count"])
        timestep_count = int(event["timestep_count"])
        shape = event.get("shape")
        if shape != [timestep_count, vertex_count]:
            raise ResultStorageError("Activation chunk shape does not match timestep and vertex counts")

        if self.vertex_count is not None and vertex_count != self.vertex_count:
            raise ResultStorageError("Activation chunks have inconsistent vertex counts")

        activations = event["activations"]
        if not isinstance(activations, bytes):
            raise ResultStorageError("Activation chunk payload must be bytes")

        matrix = np.frombuffer(activations, dtype="<f4").reshape(timestep_count, vertex_count).copy()
        self._chunks.append((int(event["timestep_start"]), matrix))
        self.vertex_count = vertex_count
        self.sample_rate_hz = float(event["sample_rate_hz"])

    def assemble(self) -> NDArray[np.float32]:
        if not self._chunks:
            raise ResultStorageError("No activation chunks were captured")

        ordered_chunks = sorted(self._chunks, key=lambda item: item[0])
        expected_start = 0
        matrices: list[NDArray[np.float32]] = []
        for timestep_start, matrix in ordered_chunks:
            if timestep_start != expected_start:
                raise ResultStorageError("Activation chunks are missing timesteps")
            matrices.append(matrix)
            expected_start += matrix.shape[0]

        return np.ascontiguousarray(np.vstack(matrices), dtype="<f4")


def serialize_activation_npz(
    matrix: NDArray[np.float32],
    *,
    sample_rate_hz: float | None,
    metadata: dict[str, Any],
) -> bytes:
    buffer = BytesIO()
    np.savez_compressed(
        buffer,
        activations=np.ascontiguousarray(matrix, dtype="<f4"),
        sample_rate_hz=np.array(sample_rate_hz if sample_rate_hz is not None else np.nan, dtype="<f4"),
        metadata=np.array([metadata], dtype=object),
    )
    return buffer.getvalue()


async def store_job_result(
    session: AsyncSession,
    job: Job,
    matrix: NDArray[np.float32],
    *,
    sample_rate_hz: float | None,
    model_name: str = "tribev2",
    model_version: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Result:
    if matrix.ndim != 2:
        raise ResultStorageError("Activation result matrix must be 2D")
    if matrix.dtype != np.dtype("float32"):
        matrix = matrix.astype("<f4", copy=False)

    s3_key = result_object_key(str(job.id))
    result_metadata = metadata or {}
    payload = serialize_activation_npz(matrix, sample_rate_hz=sample_rate_hz, metadata=result_metadata)

    last_error: Exception | None = None
    started_at = time.monotonic()
    logger.info("s3_result_save_start", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "s3_key": s3_key})
    for attempt in range(1, 3):
        try:
            _s3_client().put_object(
                Bucket=get_settings().s3_bucket_name,
                Key=s3_key,
                Body=payload,
                ContentType="application/octet-stream",
            )
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            logger.warning("s3_result_save_error", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "s3_key": s3_key, "attempt": attempt}, exc_info=exc)
    if last_error is not None:
        raise ResultStorageError(f"Failed to store result artifact: {last_error}") from last_error
    logger.info("s3_result_save_end", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "s3_key": s3_key, "duration_ms": int((time.monotonic() - started_at) * 1000)})

    result = Result(
        job_id=job.id,
        experiment_id=job.experiment_id,
        owner_id=job.owner_id,
        s3_key=s3_key,
        format="npz",
        dtype="float32",
        shape=[int(matrix.shape[0]), int(matrix.shape[1])],
        vertex_count=int(matrix.shape[1]),
        timestep_count=int(matrix.shape[0]),
        sample_rate_hz=sample_rate_hz,
        model_name=model_name,
        model_version=model_version,
        metadata_json=result_metadata,
    )
    session.add(result)
    await session.flush()
    logger.info("db_result_row_created", extra={"job_id": str(job.id), "experiment_id": str(job.experiment_id), "user_id": str(job.owner_id), "s3_key": s3_key})
    return result
