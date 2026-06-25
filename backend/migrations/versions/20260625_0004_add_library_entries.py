"""add library entries

Revision ID: 20260625_0004
Revises: 20260605_0003
Create Date: 2026-06-25 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260625_0004"
down_revision: str | None = "20260605_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("experiment_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("featured", sa.Boolean(), nullable=False),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", name="uq_library_entries_experiment_id"),
    )
    op.create_index(op.f("ix_library_entries_experiment_id"), "library_entries", ["experiment_id"], unique=False)
    op.create_index(op.f("ix_library_entries_owner_id"), "library_entries", ["owner_id"], unique=False)
    op.create_index(op.f("ix_library_entries_slug"), "library_entries", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_library_entries_slug"), table_name="library_entries")
    op.drop_index(op.f("ix_library_entries_owner_id"), table_name="library_entries")
    op.drop_index(op.f("ix_library_entries_experiment_id"), table_name="library_entries")
    op.drop_table("library_entries")
