"""Baseline migration.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline only: no domain schema yet.
    op.execute("SELECT 1")


def downgrade() -> None:
    op.execute("SELECT 1")
