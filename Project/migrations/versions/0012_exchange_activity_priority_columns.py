"""Add exchange activity priority columns.

Revision ID: 0012_exchange_activity_priority_columns
Revises: 0011_instrument_outcome_classification
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012_exchange_activity_priority_columns"
down_revision = "0011_instrument_outcome_classification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exchange",
        sa.Column("activity_priority_rank", sa.Integer(), nullable=False, server_default=sa.text("9999")),
    )
    op.add_column(
        "exchange",
        sa.Column(
            "activity_priority_score",
            sa.Numeric(18, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.alter_column("exchange", "activity_priority_rank", server_default=None)
    op.alter_column("exchange", "activity_priority_score", server_default=None)


def downgrade() -> None:
    op.drop_column("exchange", "activity_priority_score")
    op.drop_column("exchange", "activity_priority_rank")
