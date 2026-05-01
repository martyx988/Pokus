"""Instrument identity, listing, identifiers, and support state schema.

Revision ID: 0003_instrument_identity_listing
Revises: 0002_exchange_instrument_type
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_instrument_identity_listing"
down_revision = "0002_exchange_instrument_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instrument",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_type_id", sa.Integer(), nullable=False),
        sa.Column("canonical_name", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["instrument_type_id"], ["instrument_type.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "listing",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("exchange_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("venue_name", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchange.id"]),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_id", "symbol", name="uq_listing_exchange_symbol"),
        sa.UniqueConstraint("exchange_id", "instrument_id", name="uq_listing_exchange_instrument"),
    )
    op.create_table(
        "identifier_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("identifier_type", sa.String(length=64), nullable=False),
        sa.Column("identifier_value", sa.String(length=256), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instrument.id"]),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_code",
            "identifier_type",
            "identifier_value",
            name="uq_identifier_record_provider_type_value",
        ),
    )
    op.create_table(
        "supported_universe_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "supported",
                "not_yet_signal_eligible",
                "delisting_suspected",
                "removed",
                "historical_only",
                name="supported_universe_status_enum",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["listing_id"], ["listing.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id", name="uq_supported_universe_state_listing_id"),
    )

    op.alter_column("instrument", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_table("supported_universe_state")
    op.drop_table("identifier_record")
    op.drop_table("listing")
    op.drop_table("instrument")
