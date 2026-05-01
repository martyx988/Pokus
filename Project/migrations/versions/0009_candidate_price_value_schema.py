"""Candidate price value persistence schema.

Revision ID: 0009_candidate_price_value_schema
Revises: 0008_provider_attempt_attempt_key
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_candidate_price_value_schema"
down_revision = "0008_provider_attempt_attempt_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_price_value",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_key", sa.String(length=256), nullable=False),
        sa.Column("candidate_set_key", sa.String(length=256), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("provider_attempt_id", sa.Integer(), nullable=True),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("price_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("provider_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "price_type IN ('historical_adjusted_close','current_day_unadjusted_open')",
            name="ck_candidate_price_value_price_type",
        ),
        sa.CheckConstraint(
            "length(trim(candidate_key)) > 0",
            name="ck_candidate_price_value_candidate_key_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(candidate_set_key)) > 0",
            name="ck_candidate_price_value_set_key_nonempty",
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"], name="fk_candidate_price_value_listing"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], name="fk_candidate_price_value_provider"),
        sa.ForeignKeyConstraint(
            ["provider_attempt_id"],
            ["provider_attempt.id"],
            name="fk_candidate_price_value_provider_attempt",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_key", name="uq_candidate_price_value_candidate_key"),
    )


def downgrade() -> None:
    op.drop_table("candidate_price_value")
