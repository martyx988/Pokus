"""Price record schema.

Revision ID: 0005_price_record_schema
Revises: 0003_instrument_identity_listing, 0003_provider_attempt_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_price_record_schema"
down_revision = ("0003_instrument_identity_listing", "0003_provider_attempt_schema")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("price_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_attempt_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "price_type IN ('historical_adjusted_close','current_day_unadjusted_open')",
            name="ck_price_record_price_type",
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.ForeignKeyConstraint(["provider_attempt_id"], ["provider_attempt.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", "trading_date", "price_type", name="uq_price_record_listing_date_type"),
    )


def downgrade() -> None:
    op.drop_table("price_record")
