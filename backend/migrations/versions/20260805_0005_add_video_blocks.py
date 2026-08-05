"""add video blocks

Revision ID: 20260805_0005
Revises: 20260625_0004
Create Date: 2026-08-05
"""

from alembic import op


revision = "20260805_0005"
down_revision = "20260625_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE block_type ADD VALUE IF NOT EXISTS 'video'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be safely removed without rebuilding the type.
    pass
