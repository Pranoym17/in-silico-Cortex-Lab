from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


UploadKind = Literal["image", "audio"]
ImageMimeType = Literal["image/png", "image/jpeg", "image/webp"]
AudioMimeType = Literal["audio/mpeg", "audio/wav", "audio/mp4", "audio/x-m4a"]


class UploadIntentRequest(BaseModel):
    experiment_id: UUID
    block_id: UUID | None = None
    kind: UploadKind
    filename: str = Field(min_length=1, max_length=255)
    mime_type: ImageMimeType | AudioMimeType
    size_bytes: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_kind_contract(self) -> "UploadIntentRequest":
        if self.kind == "image":
            if not self.mime_type.startswith("image/"):
                raise ValueError("image uploads require an image MIME type")
            if self.size_bytes > 10 * 1024 * 1024:
                raise ValueError("image uploads cannot exceed 10MB")

        if self.kind == "audio":
            if not self.mime_type.startswith("audio/"):
                raise ValueError("audio uploads require an audio MIME type")
            if self.size_bytes > 100 * 1024 * 1024:
                raise ValueError("audio uploads cannot exceed 100MB")

        return self


class UploadIntentResponse(BaseModel):
    upload_url: str
    object_key: str
    headers: dict[str, str]
    expires_in_seconds: int
    content_hash_algorithm: Literal["sha256"] = "sha256"
