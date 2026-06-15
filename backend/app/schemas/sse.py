from typing import Literal

from pydantic import BaseModel, Field

from app.models.job import JobStatus
from app.services.error_codes import JobErrorCode


ActivationEncoding = Literal["base64-msgpack"]
ActivationDtype = Literal["float32"]


class QueuedEvent(BaseModel):
    job_id: str
    status: Literal[JobStatus.queued] = JobStatus.queued


class WarmingEvent(BaseModel):
    job_id: str
    reason: str = "modal_cold_start"
    estimated_seconds: int = Field(ge=0)


class ProgressEvent(BaseModel):
    job_id: str
    completed_blocks: int = Field(ge=0)
    total_blocks: int = Field(ge=0)
    completed_timesteps: int = Field(ge=0)


class ChunkEnvelope(BaseModel):
    encoding: ActivationEncoding = "base64-msgpack"
    payload: str


class CompleteEvent(BaseModel):
    job_id: str
    status: Literal[JobStatus.complete] = JobStatus.complete
    result_s3_key: str | None = None
    timesteps: int = Field(ge=0)
    vertex_count: int = Field(ge=0)


class ErrorEvent(BaseModel):
    job_id: str
    code: JobErrorCode
    message: str
    retryable: bool
    last_timestep: int | None = Field(default=None, ge=0)
