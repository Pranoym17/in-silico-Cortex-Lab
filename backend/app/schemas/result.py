from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResultResponse(BaseModel):
    id: UUID
    job_id: UUID
    experiment_id: UUID
    owner_id: UUID
    s3_key: str
    format: str
    dtype: str
    shape: list[int]
    vertex_count: int
    timestep_count: int
    sample_rate_hz: float | None = None
    model_name: str
    model_version: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
