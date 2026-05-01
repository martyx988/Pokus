"""Provider/exchange reliability score schema.

Revision ID: 0010_provider_exchange_reliability_score_schema
Revises: 0009_candidate_price_value_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_provider_exchange_reliability_score_schema"
down_revision = "0009_candidate_price_value_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_exchange_reliability_score",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("exchange_id", sa.Integer(), nullable=False),
        sa.Column("reliability_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("observations_count", sa.Integer(), nullable=False),
        sa.Column("last_window_key", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reliability_score >= 0 AND reliability_score <= 1",
            name="ck_provider_exchange_reliability_score_range",
        ),
        sa.CheckConstraint(
            "observations_count >= 0",
            name="ck_provider_exchange_reliability_observations_nonnegative",
        ),
        sa.CheckConstraint(
            "last_window_key IS NULL OR length(trim(last_window_key)) > 0",
            name="ck_provider_exchange_reliability_last_window_key_nonempty",
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], name="fk_provider_exchange_reliability_provider"),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchange.id"], name="fk_provider_exchange_reliability_exchange"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", "exchange_id", name="uq_provider_exchange_reliability_scope"),
    )


def downgrade() -> None:
    op.drop_table("provider_exchange_reliability_score")
