from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


Slug = str


class LibraryPublishRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=12)
    slug: Slug = Field(min_length=3, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class LibraryEntryResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str | None = None
    tags: list[str]
    featured: bool
    run_count: int
    published_at: datetime
    created_at: datetime
    updated_at: datetime



class PublicAuthorResponse(BaseModel):
    display_name: str
    avatar_url: str | None = None


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
    author: PublicAuthorResponse
    experiment_name: str
    experiment_description: str | None = None
    blocks: list[PublicLibraryExperimentBlock]


class LibraryForkResponse(BaseModel):
    experiment_id: UUID


class PublicResultResponse(BaseModel):
    format: str
    dtype: str
    shape: list[int]
    vertex_count: int
    timestep_count: int
    sample_rate_hz: float | None = None
    model_name: str
    model_version: str | None = None
    metadata: dict
    completed_at: datetime | None = None
    download_url: str
    expires_in_seconds: int


class PublicExperimentReportResponse(BaseModel):
    slug: str
    title: str
    description: str | None = None
    author: PublicAuthorResponse
    published_at: datetime
    tags: list[str]
    blocks: list[PublicLibraryExperimentBlock]
    result: PublicResultResponse | None = None
    limitations: list[str]


class PublicEmbedResponse(BaseModel):
    slug: str
    title: str
    iframe_path: str
    viewer_available: bool
