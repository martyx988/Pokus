"""Provider and provider attempt evidence schema.

Revision ID: 0003_provider_attempt_schema
Revises: 0002_exchange_instrument_type
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_provider_attempt_schema"
down_revision = "0002_exchange_instrument_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("configuration", sa.JSON(), nullable=True),
        sa.CheckConstraint("code = upper(code)", name="ck_provider_code_upper"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_provider_code"),
    )
    op.create_table(
        "provider_attempt",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("exchange_id", sa.Integer(), nullable=False),
        sa.Column("request_purpose", sa.String(length=64), nullable=False),
        sa.Column("load_type", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("result_status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("rate_limit_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stale_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("missing_values", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_provider_attempt_latency_nonnegative"),
        sa.CheckConstraint(
            "result_status IN ('success','timeout','error','rate_limited')",
            name="ck_provider_attempt_result_status",
        ),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchange.id"], name="fk_provider_attempt_exchange"),
        sa.ForeignKeyConstraint(["provider_id"], ["provider.id"], name="fk_provider_attempt_provider"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("provider", "is_active", server_default=None)
    op.alter_column("provider_attempt", "rate_limit_hit", server_default=None)
    op.alter_column("provider_attempt", "stale_data", server_default=None)
    op.alter_column("provider_attempt", "missing_values", server_default=None)


def downgrade() -> None:
    op.drop_table("provider_attempt")
    op.drop_table("provider")
