"""Universe change audit schema.

Revision ID: 0004_universe_change_audit_schema
Revises: 0003_instrument_identity_listing_schema
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_universe_change_audit_schema"
down_revision = "0003_instrument_identity_listing_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "universe_change_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "added",
                "removed",
                "excluded",
                "delisting_suspected",
                "restored",
                "degraded",
                "symbol_changed",
                "name_changed",
                "identifier_changed",
                name="universe_change_event_type_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("effective_day", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("old_state_evidence", sa.JSON(), nullable=True),
        sa.Column("new_state_evidence", sa.JSON(), nullable=True),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("exchange_id", sa.Integer(), nullable=True),
        sa.Column("instrument_type_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("trim(reason) <> ''", name="ck_universe_change_record_reason_nonempty"),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchange.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument.id"]),
        sa.ForeignKeyConstraint(["instrument_type_id"], ["instrument_type.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("universe_change_record")
