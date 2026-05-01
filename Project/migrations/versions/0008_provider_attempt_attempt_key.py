"""Add idempotency attempt key to provider_attempt.

Revision ID: 0008_provider_attempt_attempt_key
Revises: 0007_m1_merge_heads
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_provider_attempt_attempt_key"
down_revision = "0007_m1_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic defaults version_num to VARCHAR(32), but later revision IDs exceed 32 chars.
    op.alter_column("alembic_version", "version_num", type_=sa.String(length=64), existing_type=sa.String(length=32))

    op.add_column(
        "provider_attempt",
        sa.Column(
            "attempt_key",
            sa.String(length=128),
            nullable=False,
            server_default="migration_default_attempt_key",
        ),
    )
    op.create_unique_constraint("uq_provider_attempt_attempt_key", "provider_attempt", ["attempt_key"])
    op.create_check_constraint(
        "ck_provider_attempt_attempt_key_nonempty",
        "provider_attempt",
        "length(trim(attempt_key)) > 0",
    )
    op.alter_column("provider_attempt", "attempt_key", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_provider_attempt_attempt_key_nonempty", "provider_attempt", type_="check")
    op.drop_constraint("uq_provider_attempt_attempt_key", "provider_attempt", type_="unique")
    op.drop_column("provider_attempt", "attempt_key")
    op.alter_column("alembic_version", "version_num", type_=sa.String(length=32), existing_type=sa.String(length=64))
