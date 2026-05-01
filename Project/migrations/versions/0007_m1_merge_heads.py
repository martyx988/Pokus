"""Merge Milestone 1 migration heads.

Revision ID: 0007_m1_merge_heads
Revises: 0003_runtime_heartbeats, 0004_admin_command_audit_record, 0004_publication_quality, 0004_universe_change_audit, 0006_signal_event_and_statistic
Create Date: 2026-05-01
"""

from __future__ import annotations

# revision identifiers, used by Alembic.
revision = "0007_m1_merge_heads"
down_revision = (
    "0003_runtime_heartbeats",
    "0004_admin_command_audit_record",
    "0004_publication_quality",
    "0004_universe_change_audit",
    "0006_signal_event_and_statistic",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge revision only; no schema changes.
    return None


def downgrade() -> None:
    # Merge revision only; no schema changes to revert.
    return None
