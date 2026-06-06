from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Result(TimestampMixin, Base):
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("job_id", name="uq_results_job_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("jobs.id"), index=True, nullable=False)
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id"),
        index=True,
        nullable=False,
    )
    owner_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    format: Mapped[str] = mapped_column(String(64), default="npz", nullable=False)
    dtype: Mapped[str] = mapped_column(String(64), default="float32", nullable=False)
    shape: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    vertex_count: Mapped[int] = mapped_column(Integer, nullable=False)
    timestep_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_rate_hz: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str] = mapped_column(String(255), default="tribev2", nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    job = relationship("Job", back_populates="results")
    experiment = relationship("Experiment", back_populates="results")
    owner = relationship("User", back_populates="results")
