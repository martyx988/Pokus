"""Signal event and statistic schema.

Revision ID: 0006_signal_event_and_statistic_schema
Revises: 0005_price_record_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_signal_event_and_statistic_schema"
down_revision = "0005_price_record_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("algorithm_context", sa.JSON(), nullable=True),
        sa.Column("signal_outcome", sa.String(length=32), nullable=False),
        sa.Column("signal_type", sa.String(length=32), nullable=True),
        sa.CheckConstraint(
            "signal_outcome IN ('signal','no_signal','insufficient_history')",
            name="ck_signal_event_signal_outcome",
        ),
        sa.CheckConstraint(
            "signal_type IS NULL OR signal_type IN ('Dip','Skyrocket')",
            name="ck_signal_event_signal_type",
        ),
        sa.CheckConstraint(
            "(signal_outcome = 'signal' AND signal_type IS NOT NULL) "
            "OR (signal_outcome IN ('no_signal','insufficient_history') AND signal_type IS NULL)",
            name="ck_signal_event_outcome_signal_type_match",
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "listing_id",
            "trading_date",
            "algorithm_version",
            "signal_type",
            name="uq_signal_event_listing_date_algo_signal_type",
        ),
    )

    op.create_table(
        "signal_statistic",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=64), nullable=False),
        sa.Column("statistic_name", sa.String(length=64), nullable=False),
        sa.Column("statistic_value", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "listing_id",
            "trading_date",
            "algorithm_version",
            "statistic_name",
            name="uq_signal_statistic_listing_date_algo_name",
        ),
    )


def downgrade() -> None:
    op.drop_table("signal_statistic")
    op.drop_table("signal_event")
