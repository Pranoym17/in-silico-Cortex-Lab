"""initial foundation tables

Revision ID: 20260517_0001
Revises:
Create Date: 2026-05-17 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260517_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

experiment_status = postgresql.ENUM("draft", "ready", "archived", name="experiment_status")
block_type = postgresql.ENUM("image", "text", "audio", name="block_type")
job_status = postgresql.ENUM("queued", "warming", "running", "streaming", "complete", "failed", "cancelled", name="job_status")


def upgrade() -> None:
    bind = op.get_bind()
    experiment_status.create(bind, checkfirst=True)
    block_type.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("supabase_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_supabase_user_id"), "users", ["supabase_user_id"], unique=True)

    op.create_table(
        "experiments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", postgresql.ENUM("draft", "ready", "archived", name="experiment_status", create_type=False), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_experiments_owner_id"), "experiments", ["owner_id"], unique=False)
    op.create_index(op.f("ix_experiments_slug"), "experiments", ["slug"], unique=True)

    op.create_table(
        "blocks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("type", postgresql.ENUM("image", "text", "audio", name="block_type", create_type=False), nullable=False),
        sa.Column("condition", sa.String(length=255), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_blocks_content_hash"), "blocks", ["content_hash"], unique=False)
    op.create_index(op.f("ix_blocks_experiment_id"), "blocks", ["experiment_id"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("status", postgresql.ENUM("queued", "warming", "running", "streaming", "complete", "failed", "cancelled", name="job_status", create_type=False), nullable=False),
        sa.Column("error_code", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_experiment_id"), "jobs", ["experiment_id"], unique=False)
    op.create_index(op.f("ix_jobs_owner_id"), "jobs", ["owner_id"], unique=False)

    op.create_table(
        "results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("s3_key", sa.String(length=2048), nullable=True),
        sa.Column("timesteps", sa.Integer(), nullable=True),
        sa.Column("vertex_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_results_experiment_id"), "results", ["experiment_id"], unique=False)
    op.create_index(op.f("ix_results_job_id"), "results", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_results_job_id"), table_name="results")
    op.drop_index(op.f("ix_results_experiment_id"), table_name="results")
    op.drop_table("results")

    op.drop_index(op.f("ix_jobs_owner_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_experiment_id"), table_name="jobs")
    op.drop_table("jobs")

    op.drop_index(op.f("ix_blocks_experiment_id"), table_name="blocks")
    op.drop_index(op.f("ix_blocks_content_hash"), table_name="blocks")
    op.drop_table("blocks")

    op.drop_index(op.f("ix_experiments_slug"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_owner_id"), table_name="experiments")
    op.drop_table("experiments")

    op.drop_index(op.f("ix_users_supabase_user_id"), table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    job_status.drop(bind, checkfirst=True)
    block_type.drop(bind, checkfirst=True)
    experiment_status.drop(bind, checkfirst=True)
