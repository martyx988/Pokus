"""Exchange and instrument type reference schema.

Revision ID: 0002_exchange_instrument_type
Revises: 0001_baseline
Create Date: 2026-05-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_exchange_instrument_type"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_launch_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("code = upper(code)", name="ck_exchange_code_upper"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_exchange_code"),
    )
    op.create_table(
        "instrument_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_launch_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("code = upper(code)", name="ck_instrument_type_code_upper"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_instrument_type_code"),
    )

    op.bulk_insert(
        sa.table(
            "exchange",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("is_launch_active", sa.Boolean),
        ),
        [
            {"code": "NYSE", "name": "New York Stock Exchange", "is_launch_active": True},
            {"code": "NASDAQ", "name": "Nasdaq", "is_launch_active": True},
            {"code": "PSE", "name": "Prague Stock Exchange", "is_launch_active": True},
            {"code": "CRY", "name": "Synthetic Crypto Exchange", "is_launch_active": False},
        ],
    )
    op.bulk_insert(
        sa.table(
            "instrument_type",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("is_launch_active", sa.Boolean),
        ),
        [
            {"code": "STOCK", "name": "Stock", "is_launch_active": True},
            {"code": "ETF", "name": "ETF", "is_launch_active": True},
            {"code": "ETN", "name": "ETN", "is_launch_active": True},
            {"code": "CRYPTO", "name": "Crypto", "is_launch_active": False},
        ],
    )

    op.alter_column("exchange", "is_launch_active", server_default=None)
    op.alter_column("instrument_type", "is_launch_active", server_default=None)


def downgrade() -> None:
    op.drop_table("instrument_type")
    op.drop_table("exchange")
