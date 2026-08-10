"""add library moderation

Revision ID: 20260810_0006
Revises: 20260805_0005
Create Date: 2026-08-10 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260810_0006"
down_revision: str | None = "20260805_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("library_entries", sa.Column("moderation_status", sa.String(length=32), server_default="published", nullable=False))
    op.create_index(op.f("ix_library_entries_moderation_status"), "library_entries", ["moderation_status"], unique=False)
    op.create_table(
        "library_flags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entry_id", sa.UUID(), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="open", nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entry_id"], ["library_entries.id"]),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_library_flags_entry_id"), "library_flags", ["entry_id"], unique=False)
    op.create_index(op.f("ix_library_flags_reporter_id"), "library_flags", ["reporter_id"], unique=False)
    op.create_index(op.f("ix_library_flags_status"), "library_flags", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_library_flags_status"), table_name="library_flags")
    op.drop_index(op.f("ix_library_flags_reporter_id"), table_name="library_flags")
    op.drop_index(op.f("ix_library_flags_entry_id"), table_name="library_flags")
    op.drop_table("library_flags")
    op.drop_index(op.f("ix_library_entries_moderation_status"), table_name="library_entries")
    op.drop_column("library_entries", "moderation_status")
