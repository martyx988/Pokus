"""Add source-validation evidence and classification record schema.

Revision ID: 0014_source_validation_record_schema
Revises: 0013_quality_check_publication_block_fields
Create Date: 2026-05-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0014_source_validation_record_schema"
down_revision = "0013_quality_check_publication_block_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_validation_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("validation_run_key", sa.String(length=128), nullable=False),
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("auth_required", sa.Boolean(), nullable=False),
        sa.Column("quota_rate_limit_notes", sa.Text(), nullable=False),
        sa.Column("speed_notes", sa.Text(), nullable=False),
        sa.Column("exchange_coverage_notes", sa.Text(), nullable=False),
        sa.Column("observed_latency_ms", sa.Integer(), nullable=True),
        sa.Column("classification_verdict", sa.String(length=32), nullable=False),
        sa.Column("assigned_role", sa.String(length=64), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(validation_run_key)) > 0",
            name="ck_source_validation_record_run_key_nonempty",
        ),
        sa.CheckConstraint(
            "source_code = upper(source_code)",
            name="ck_source_validation_record_source_code_upper",
        ),
        sa.CheckConstraint(
            "length(trim(source_code)) > 0",
            name="ck_source_validation_record_source_code_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(quota_rate_limit_notes)) > 0",
            name="ck_source_validation_record_quota_notes_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(speed_notes)) > 0",
            name="ck_source_validation_record_speed_notes_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(exchange_coverage_notes)) > 0",
            name="ck_source_validation_record_exchange_notes_nonempty",
        ),
        sa.CheckConstraint(
            "classification_verdict IN ('promote','fallback_only','validation_only','not_for_universe_loader','reject')",
            name="ck_source_validation_record_classification_verdict",
        ),
        sa.CheckConstraint(
            "assigned_role IS NULL OR assigned_role IN "
            "('primary_discovery','metadata_enrichment','symbology_normalization',"
            "'fallback_discovery','validation_only','not_for_universe_loader')",
            name="ck_source_validation_record_assigned_role",
        ),
        sa.CheckConstraint(
            "observed_latency_ms IS NULL OR observed_latency_ms >= 0",
            name="ck_source_validation_record_latency_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "validation_run_key",
            "source_code",
            name="uq_source_validation_record_run_source",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_validation_record")
