from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.block import BlockType

ContentHash = Annotated[str, Field(pattern=r"^sha256:[a-fA-F0-9]{3,}$", max_length=255)]


class BlockBase(BaseModel):
    type: BlockType
    condition: str | None = Field(default=None, max_length=255)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)
    content_hash: ContentHash | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_type_specific_constraints(self) -> "BlockBase":
        if self.type == BlockType.image and not 500 <= self.duration_ms <= 30000:
            raise ValueError("image block duration must be between 500ms and 30000ms")

        if self.type == BlockType.audio and self.duration_ms > 60000:
            raise ValueError("audio block duration cannot exceed 60000ms")

        if self.type == BlockType.text:
            text = self.payload.get("text")
            if text is not None and isinstance(text, str) and len(text.split()) > 1024:
                raise ValueError("text blocks cannot exceed 1024 words")

        return self


class BlockCreate(BlockBase):
    pass


class TemplateBlock(BlockBase):
    id: UUID | None = None


class BlockUpdate(BaseModel):
    condition: str | None = Field(default=None, max_length=255)
    start_ms: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, gt=0)
    content_hash: ContentHash | None = None
    payload: dict[str, Any] | None = None


class BlockResponse(BaseModel):
    id: UUID
    experiment_id: UUID
    type: BlockType
    condition: str | None = None
    start_ms: int
    duration_ms: int
    content_hash: str | None = None
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlockReorderItem(BaseModel):
    id: UUID
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(gt=0)


class BlockReorderRequest(BaseModel):
    blocks: list[BlockReorderItem] = Field(min_length=1, max_length=50)


class TemplateApplyRequest(BaseModel):
    mode: Literal["append", "replace"]
    blocks: list[TemplateBlock] = Field(max_length=50)

    @model_validator(mode="after")
    def validate_append_has_blocks(self) -> "TemplateApplyRequest":
        if self.mode == "append" and not self.blocks:
            raise ValueError("append templates require at least one block")
        if self.mode == "append" and any(block.id is not None for block in self.blocks):
            raise ValueError("append templates cannot specify block IDs")
        block_ids = [block.id for block in self.blocks if block.id is not None]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("template block IDs must be unique")
        return self
