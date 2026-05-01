"""Admin command and audit record schema.

Revision ID: 0004_admin_command_audit_record
Revises: 0002_load_jobs, 0003_provider_attempt_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_admin_command_audit_record"
down_revision = ("0002_load_jobs", "0003_provider_attempt_schema")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_commands",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("command_type", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("load_job_id", sa.BigInteger(), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "command_type IN ("
            "'configuration_change',"
            "'validation_trigger',"
            "'historical_reprocess',"
            "'retention_action',"
            "'job_retry',"
            "'job_cancel',"
            "'job_mark_failed'"
            ")",
            name="ck_admin_commands_command_type",
        ),
        sa.CheckConstraint(
            "command_type NOT IN ("
            "'configuration_change','historical_reprocess','retention_action','job_retry','job_cancel','job_mark_failed'"
            ") OR (reason IS NOT NULL AND btrim(reason) <> '')",
            name="ck_admin_commands_reason_required_mutating",
        ),
        sa.ForeignKeyConstraint(["load_job_id"], ["load_jobs.id"], name="fk_admin_commands_load_job"),
    )
    op.create_index("ix_admin_commands_command_type", "admin_commands", ["command_type"], unique=False)

    op.create_table(
        "audit_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("admin_command_id", sa.BigInteger(), nullable=True),
        sa.Column("load_job_id", sa.BigInteger(), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "metadata IS NULL OR ("
            "metadata::text NOT ILIKE '%password%' AND "
            "metadata::text NOT ILIKE '%secret%' AND "
            "metadata::text NOT ILIKE '%token%' AND "
            "metadata::text NOT ILIKE '%authorization%' AND "
            "metadata::text NOT ILIKE '%cookie%' AND "
            "metadata::text NOT ILIKE '%api_key%'"
            ")",
            name="ck_audit_records_metadata_no_secrets",
        ),
        sa.ForeignKeyConstraint(["admin_command_id"], ["admin_commands.id"], name="fk_audit_records_admin_command"),
        sa.ForeignKeyConstraint(["load_job_id"], ["load_jobs.id"], name="fk_audit_records_load_job"),
    )
    op.create_index("ix_audit_records_action", "audit_records", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_records_action", table_name="audit_records")
    op.drop_table("audit_records")
    op.drop_index("ix_admin_commands_command_type", table_name="admin_commands")
    op.drop_table("admin_commands")
