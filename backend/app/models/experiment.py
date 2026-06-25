import enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ExperimentStatus(str, enum.Enum):
    draft = "draft"
    ready = "ready"
    archived = "archived"


class Experiment(TimestampMixin, Base):
    __tablename__ = "experiments"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, name="experiment_status"),
        default=ExperimentStatus.draft,
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)

    owner = relationship("User", back_populates="experiments")
    blocks = relationship("Block", back_populates="experiment", cascade="all, delete-orphan", order_by="Block.start_ms")
    jobs = relationship("Job", back_populates="experiment", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="experiment", cascade="all, delete-orphan")
    library_entry = relationship("LibraryEntry", back_populates="experiment", cascade="all, delete-orphan", uselist=False)

