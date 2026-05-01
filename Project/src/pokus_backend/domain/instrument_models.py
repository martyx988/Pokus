from __future__ import annotations

import enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pokus_backend.domain.reference_models import Base


class SupportedUniverseStatus(str, enum.Enum):
    SUPPORTED = "supported"
    NOT_YET_SIGNAL_ELIGIBLE = "not_yet_signal_eligible"
    DELISTING_SUSPECTED = "delisting_suspected"
    REMOVED = "removed"
    HISTORICAL_ONLY = "historical_only"


class Instrument(Base):
    __tablename__ = "instrument"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_type_id: Mapped[int] = mapped_column(ForeignKey("instrument_type.id"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    listings: Mapped[list["Listing"]] = relationship(back_populates="instrument")
    identifiers: Mapped[list["IdentifierRecord"]] = relationship(back_populates="instrument")


class Listing(Base):
    __tablename__ = "listing"
    __table_args__ = (
        UniqueConstraint("exchange_id", "symbol", name="uq_listing_exchange_symbol"),
        UniqueConstraint("exchange_id", "instrument_id", name="uq_listing_exchange_instrument"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instrument.id"), nullable=False)
    exchange_id: Mapped[int] = mapped_column(ForeignKey("exchange.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    venue_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    instrument: Mapped["Instrument"] = relationship(back_populates="listings")
    identifiers: Mapped[list["IdentifierRecord"]] = relationship(back_populates="listing")
    support_state: Mapped["SupportedUniverseState"] = relationship(back_populates="listing", uselist=False)
    price_records: Mapped[list["PriceRecord"]] = relationship(back_populates="listing")


class IdentifierRecord(Base):
    __tablename__ = "identifier_record"
    __table_args__ = (
        UniqueConstraint(
            "provider_code",
            "identifier_type",
            "identifier_value",
            name="uq_identifier_record_provider_type_value",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instrument.id"), nullable=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listing.id"), nullable=True)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(256), nullable=False)

    instrument: Mapped["Instrument | None"] = relationship(back_populates="identifiers")
    listing: Mapped["Listing | None"] = relationship(back_populates="identifiers")


class SupportedUniverseState(Base):
    __tablename__ = "supported_universe_state"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), unique=True, nullable=False)
    status: Mapped[SupportedUniverseStatus] = mapped_column(
        Enum(
            SupportedUniverseStatus,
            name="supported_universe_status_enum",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    effective_from: Mapped[Date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    listing: Mapped["Listing"] = relationship(back_populates="support_state")


class PriceRecord(Base):
    __tablename__ = "price_record"
    __table_args__ = (
        CheckConstraint(
            "price_type IN ('historical_adjusted_close','current_day_unadjusted_open')",
            name="ck_price_record_price_type",
        ),
        UniqueConstraint(
            "listing_id",
            "trading_date",
            "price_type",
            name="uq_price_record_listing_date_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing.id"), nullable=False)
    trading_date: Mapped[Date] = mapped_column(Date, nullable=False)
    price_type: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider_attempt_id: Mapped[int | None] = mapped_column(ForeignKey("provider_attempt.id"), nullable=True)

    listing: Mapped["Listing"] = relationship(back_populates="price_records")
    provider_attempt: Mapped["ProviderAttempt | None"] = relationship()

