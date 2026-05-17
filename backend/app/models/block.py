import enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class BlockType(str, enum.Enum):
    image = "image"
    text = "text"
    audio = "audio"


class Block(TimestampMixin, Base):
    __tablename__ = "blocks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id"),
        index=True,
        nullable=False,
    )
    type: Mapped[BlockType] = mapped_column(Enum(BlockType, name="block_type"), nullable=False)
    condition: Mapped[str | None] = mapped_column(String(255))
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(255), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    experiment = relationship("Experiment", back_populates="blocks")

