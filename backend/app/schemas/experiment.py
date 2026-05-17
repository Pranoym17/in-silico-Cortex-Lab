from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.experiment import ExperimentStatus


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ExperimentStatus | None = None


class ExperimentResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    description: str | None = None
    status: ExperimentStatus
    is_public: bool
    slug: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

