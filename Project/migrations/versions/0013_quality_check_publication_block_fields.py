"""Add quality-check publication block fields.

Revision ID: 0013_quality_check_publication_block_fields
Revises: 0012_exchange_activity_priority_columns
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0013_quality_check_publication_block_fields"
down_revision = "0012_exchange_activity_priority_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quality_check",
        sa.Column("publication_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "quality_check",
        sa.Column("publication_blocked_reason", sa.Text(), nullable=True),
    )
    op.alter_column("quality_check", "publication_blocked", server_default=None)


def downgrade() -> None:
    op.drop_column("quality_check", "publication_blocked_reason")
    op.drop_column("quality_check", "publication_blocked")
