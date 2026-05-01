"""Add opening-load outcome classification fields.

Revision ID: 0011_instrument_outcome_classification
Revises: 0010_provider_exchange_reliability_score_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_instrument_outcome_classification"
down_revision = "0010_provider_exchange_reliability_score_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instrument_load_outcome",
        sa.Column("outcome_class", sa.String(length=32), nullable=False, server_default=sa.text("'missing'")),
    )
    op.add_column(
        "instrument_load_outcome",
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "ck_instrument_load_outcome_outcome_class",
        "instrument_load_outcome",
        "outcome_class IN ('success','missing','stale','halted','suspended','late_open','provider_failed')",
    )
    op.alter_column("instrument_load_outcome", "outcome_class", server_default=None)
    op.alter_column("instrument_load_outcome", "is_terminal", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_instrument_load_outcome_outcome_class", "instrument_load_outcome", type_="check")
    op.drop_column("instrument_load_outcome", "is_terminal")
    op.drop_column("instrument_load_outcome", "outcome_class")
