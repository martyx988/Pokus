"""Add load_jobs table and constraints.

Revision ID: 0002_load_jobs
Revises: 0001_baseline
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_load_jobs"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "load_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("request_timeout_seconds", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_token", sa.Text(), nullable=True),
        sa.Column("lock_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "state IN ('queued','running','retry_wait','succeeded','failed','cancelled','stale_abandoned')",
            name="ck_load_jobs_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_load_jobs_attempt_count_nonnegative"),
        sa.CheckConstraint("max_attempts >= 0", name="ck_load_jobs_max_attempts_nonnegative"),
        sa.CheckConstraint(
            "request_timeout_seconds > 0",
            name="ck_load_jobs_request_timeout_positive",
        ),
    )
    op.create_index(
        "uq_load_jobs_active_idempotency",
        "load_jobs",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("state NOT IN ('succeeded','failed','cancelled')"),
    )


def downgrade() -> None:
    op.drop_index("uq_load_jobs_active_idempotency", table_name="load_jobs")
    op.drop_table("load_jobs")

