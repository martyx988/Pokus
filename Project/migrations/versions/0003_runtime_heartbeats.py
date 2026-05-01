"""Add runtime_heartbeats table.

Revision ID: 0003_runtime_heartbeats
Revises: 0002_load_jobs
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_runtime_heartbeats"
down_revision = "0002_load_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_heartbeats",
        sa.Column("role", sa.Text(), nullable=False, primary_key=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('worker', 'scheduler')", name="ck_runtime_heartbeats_role"),
    )


def downgrade() -> None:
    op.drop_table("runtime_heartbeats")
