"""Add exchange-day load aggregate and instrument outcome tables.

Revision ID: 0003_exchange_day_load_outcomes
Revises: 0002_exchange_instrument_type, 0002_load_jobs
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_exchange_day_load_outcomes"
down_revision = ("0002_exchange_instrument_type", "0002_load_jobs")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_day_load",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exchange_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("load_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'not_started'")),
        sa.Column("eligible_instrument_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchange.id"], name="fk_exchange_day_load_exchange_id"),
        sa.ForeignKeyConstraint(["job_id"], ["load_jobs.id"], name="fk_exchange_day_load_job_id"),
        sa.CheckConstraint(
            "load_type IN ('daily_open','historical_close')",
            name="ck_exchange_day_load_load_type",
        ),
        sa.CheckConstraint(
            "status IN ('not_started','in_progress','market_closed','partial_problematic','ready','failed')",
            name="ck_exchange_day_load_status",
        ),
        sa.CheckConstraint(
            "eligible_instrument_count >= 0",
            name="ck_exchange_day_load_eligible_count_nonnegative",
        ),
        sa.CheckConstraint(
            "succeeded_count >= 0",
            name="ck_exchange_day_load_succeeded_count_nonnegative",
        ),
        sa.CheckConstraint(
            "failed_count >= 0",
            name="ck_exchange_day_load_failed_count_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_exchange_day_load_duration_nonnegative",
        ),
        sa.UniqueConstraint(
            "exchange_id",
            "trading_date",
            "load_type",
            name="uq_exchange_day_load_exchange_date_type",
        ),
    )
    op.create_table(
        "instrument_load_outcome",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exchange_day_load_id", sa.BigInteger(), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["exchange_day_load_id"],
            ["exchange_day_load.id"],
            name="fk_instrument_load_outcome_exchange_day_load_id",
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"], name="fk_instrument_load_outcome_listing_id"),
        sa.ForeignKeyConstraint(["job_id"], ["load_jobs.id"], name="fk_instrument_load_outcome_job_id"),
        sa.CheckConstraint(
            "outcome IN ('pending','in_progress','succeeded','failed','cancelled')",
            name="ck_instrument_load_outcome_outcome",
        ),
        sa.UniqueConstraint(
            "exchange_day_load_id",
            "listing_id",
            name="uq_instrument_load_outcome_exchange_day_load_listing",
        ),
    )

    op.alter_column("exchange_day_load", "status", server_default=None)
    op.alter_column("exchange_day_load", "eligible_instrument_count", server_default=None)
    op.alter_column("exchange_day_load", "succeeded_count", server_default=None)
    op.alter_column("exchange_day_load", "failed_count", server_default=None)
    op.alter_column("instrument_load_outcome", "outcome", server_default=None)


def downgrade() -> None:
    op.drop_table("instrument_load_outcome")
    op.drop_table("exchange_day_load")
