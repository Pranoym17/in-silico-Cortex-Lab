"""expand results metadata

Revision ID: 20260605_0003
Revises: 20260521_0002
Create Date: 2026-06-05 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260605_0003"
down_revision: str | None = "20260521_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("results", sa.Column("owner_id", sa.UUID(), nullable=True))
    op.add_column("results", sa.Column("format", sa.String(length=64), nullable=True))
    op.add_column("results", sa.Column("dtype", sa.String(length=64), nullable=True))
    op.add_column("results", sa.Column("shape", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("results", sa.Column("timestep_count", sa.Integer(), nullable=True))
    op.add_column("results", sa.Column("sample_rate_hz", sa.Float(), nullable=True))
    op.add_column("results", sa.Column("model_name", sa.String(length=255), nullable=True))
    op.add_column("results", sa.Column("model_version", sa.String(length=255), nullable=True))
    op.add_column("results", sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.execute(
        """
        UPDATE results
        SET owner_id = jobs.owner_id
        FROM jobs
        WHERE results.job_id = jobs.id
        """
    )
    op.execute("UPDATE results SET format = 'npz' WHERE format IS NULL")
    op.execute("UPDATE results SET dtype = 'float32' WHERE dtype IS NULL")
    op.execute("UPDATE results SET shape = '[]'::jsonb WHERE shape IS NULL")
    op.execute("UPDATE results SET timestep_count = COALESCE(timesteps, 0) WHERE timestep_count IS NULL")
    op.execute("UPDATE results SET s3_key = concat('legacy/results/', id::text, '.npz') WHERE s3_key IS NULL")
    op.execute("UPDATE results SET vertex_count = 0 WHERE vertex_count IS NULL")
    op.execute("UPDATE results SET model_name = 'tribev2' WHERE model_name IS NULL")
    op.execute("UPDATE results SET metadata_json = '{}'::jsonb WHERE metadata_json IS NULL")

    op.alter_column("results", "owner_id", nullable=False)
    op.alter_column("results", "s3_key", nullable=False)
    op.alter_column("results", "format", nullable=False)
    op.alter_column("results", "dtype", nullable=False)
    op.alter_column("results", "shape", nullable=False)
    op.alter_column("results", "vertex_count", nullable=False)
    op.alter_column("results", "timestep_count", nullable=False)
    op.alter_column("results", "model_name", nullable=False)
    op.alter_column("results", "metadata_json", nullable=False)

    op.create_index(op.f("ix_results_owner_id"), "results", ["owner_id"], unique=False)
    op.create_foreign_key(op.f("fk_results_owner_id_users"), "results", "users", ["owner_id"], ["id"])
    op.create_unique_constraint("uq_results_job_id", "results", ["job_id"])
    op.drop_column("results", "timesteps")


def downgrade() -> None:
    op.add_column("results", sa.Column("timesteps", sa.Integer(), nullable=True))
    op.execute("UPDATE results SET timesteps = timestep_count")
    op.drop_constraint("uq_results_job_id", "results", type_="unique")
    op.drop_constraint(op.f("fk_results_owner_id_users"), "results", type_="foreignkey")
    op.drop_index(op.f("ix_results_owner_id"), table_name="results")

    op.alter_column("results", "s3_key", nullable=True)
    op.alter_column("results", "vertex_count", nullable=True)
    op.drop_column("results", "metadata_json")
    op.drop_column("results", "model_version")
    op.drop_column("results", "model_name")
    op.drop_column("results", "sample_rate_hz")
    op.drop_column("results", "timestep_count")
    op.drop_column("results", "shape")
    op.drop_column("results", "dtype")
    op.drop_column("results", "format")
    op.drop_column("results", "owner_id")
