from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


Slug = str


class LibraryPublishRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=12)
    slug: Slug = Field(min_length=3, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class LibraryEntryResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    owner_id: UUID
    slug: str
    title: str
    description: str | None = None
    tags: list[str]
    featured: bool
    run_count: int
    published_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LibraryListResponse(BaseModel):
    items: list[LibraryEntryResponse]


class PublicLibraryExperimentBlock(BaseModel):
    id: UUID
    type: str
    condition: str | None = None
    start_ms: int
    duration_ms: int
    payload: dict


class LibraryDetailResponse(BaseModel):
    entry: LibraryEntryResponse
    experiment_name: str
    experiment_description: str | None = None
    blocks: list[PublicLibraryExperimentBlock]


class LibraryForkResponse(BaseModel):
    experiment_id: UUID
