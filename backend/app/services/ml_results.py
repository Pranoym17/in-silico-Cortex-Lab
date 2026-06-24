from dataclasses import dataclass
from io import BytesIO

import boto3
import numpy as np
from numpy.typing import NDArray
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.result import Result
from app.models.user import User
from app.services.result_storage import ResultStorageError
from app.services.results import get_result_for_owned_job


class MlResultLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResultActivationMatrix:
    result: Result
    activations: NDArray[np.float32]


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


def download_result_npz(s3_key: str) -> bytes:
    settings = get_settings()
    try:
        response = _s3_client().get_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        return response["Body"].read()
    except Exception as exc:
        raise MlResultLoadError(f"Failed to load result artifact: {exc}") from exc


def parse_activation_npz(payload: bytes, result: Result) -> NDArray[np.float32]:
    try:
        with np.load(BytesIO(payload), allow_pickle=False) as archive:
            if "activations" not in archive:
                raise MlResultLoadError("Result artifact is missing activations")
            activations = np.asarray(archive["activations"], dtype="<f4")
    except MlResultLoadError:
        raise
    except Exception as exc:
        raise MlResultLoadError(f"Failed to decode result artifact: {exc}") from exc

    if activations.ndim != 2:
        raise MlResultLoadError("Result activations must be a 2D matrix")
    if list(activations.shape) != list(result.shape):
        raise MlResultLoadError("Result activation matrix shape does not match metadata")
    if int(activations.shape[1]) != int(result.vertex_count):
        raise MlResultLoadError("Result activation vertex count does not match metadata")
    if int(activations.shape[0]) != int(result.timestep_count):
        raise MlResultLoadError("Result activation timestep count does not match metadata")

    return np.ascontiguousarray(activations, dtype="<f4")


async def load_owned_result_matrix(
    session: AsyncSession,
    owner: User,
    job_id,
) -> ResultActivationMatrix:
    result = await get_result_for_owned_job(session, owner, job_id)
    try:
        matrix = parse_activation_npz(download_result_npz(result.s3_key), result)
    except MlResultLoadError:
        raise
    except ResultStorageError as exc:
        raise MlResultLoadError(str(exc)) from exc
    return ResultActivationMatrix(result=result, activations=matrix)
