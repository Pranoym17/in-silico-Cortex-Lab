from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Result(TimestampMixin, Base):
    __tablename__ = "results"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("jobs.id"), index=True, nullable=False)
    experiment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("experiments.id"),
        index=True,
        nullable=False,
    )
    s3_key: Mapped[str | None] = mapped_column(String(2048))
    timesteps: Mapped[int | None] = mapped_column(Integer)
    vertex_count: Mapped[int | None] = mapped_column(Integer)

    job = relationship("Job", back_populates="results")
    experiment = relationship("Experiment", back_populates="results")

