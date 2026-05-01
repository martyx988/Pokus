"""Add publication and quality-check schema.

Revision ID: 0004_publication_and_quality_schema
Revises: 0003_exchange_day_load_and_outcomes
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_publication_and_quality_schema"
down_revision = "0003_exchange_day_load_and_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publication_record",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exchange_day_load_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'unpublished'")),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["exchange_day_load_id"],
            ["exchange_day_load.id"],
            name="fk_publication_record_exchange_day_load_id",
        ),
        sa.CheckConstraint(
            "status IN ('unpublished','ready','blocked','failed','market_closed','published')",
            name="ck_publication_record_status",
        ),
        sa.UniqueConstraint("exchange_day_load_id", name="uq_publication_record_exchange_day_load"),
    )
    op.create_table(
        "quality_check",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exchange_day_load_id", sa.BigInteger(), nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("succeeded_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("coverage_percent", sa.Float(), nullable=False),
        sa.Column("correctness_result", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("benchmark_mismatch_percent", sa.Float(), nullable=True),
        sa.Column("benchmark_mismatch_summary", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["exchange_day_load_id"],
            ["exchange_day_load.id"],
            name="fk_quality_check_exchange_day_load_id",
        ),
        sa.CheckConstraint(
            "coverage_percent >= 0 AND coverage_percent <= 100",
            name="ck_quality_check_coverage_percent_range",
        ),
        sa.CheckConstraint(
            "eligible_count >= 0",
            name="ck_quality_check_eligible_count_nonnegative",
        ),
        sa.CheckConstraint(
            "succeeded_count >= 0",
            name="ck_quality_check_succeeded_count_nonnegative",
        ),
        sa.CheckConstraint(
            "failed_count >= 0",
            name="ck_quality_check_failed_count_nonnegative",
        ),
        sa.CheckConstraint(
            "correctness_result IN ('pending','passed','failed')",
            name="ck_quality_check_correctness_result",
        ),
        sa.CheckConstraint(
            "benchmark_mismatch_percent IS NULL OR "
            "(benchmark_mismatch_percent >= 0 AND benchmark_mismatch_percent <= 100)",
            name="ck_quality_check_benchmark_mismatch_percent_range",
        ),
        sa.UniqueConstraint("exchange_day_load_id", name="uq_quality_check_exchange_day_load"),
    )

    op.alter_column("publication_record", "status", server_default=None)
    op.alter_column("quality_check", "correctness_result", server_default=None)


def downgrade() -> None:
    op.drop_table("quality_check")
    op.drop_table("publication_record")
