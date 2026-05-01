from __future__ import annotations

import enum

from sqlalchemy import JSON, CheckConstraint, Date, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pokus_backend.domain.reference_models import Base


class UniverseChangeEventType(str, enum.Enum):
    ADDED = "added"
    REMOVED = "removed"
    EXCLUDED = "excluded"
    DELISTING_SUSPECTED = "delisting_suspected"
    RESTORED = "restored"
    DEGRADED = "degraded"
    SYMBOL_CHANGED = "symbol_changed"
    NAME_CHANGED = "name_changed"
    IDENTIFIER_CHANGED = "identifier_changed"


class UniverseChangeRecord(Base):
    __tablename__ = "universe_change_record"
    __table_args__ = (
        CheckConstraint("trim(reason) <> ''", name="ck_universe_change_record_reason_nonempty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[UniverseChangeEventType] = mapped_column(
        Enum(
            UniverseChangeEventType,
            name="universe_change_event_type_enum",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    effective_day: Mapped[Date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_state_evidence: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    new_state_evidence: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instrument.id"), nullable=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listing.id"), nullable=True)
    exchange_id: Mapped[int | None] = mapped_column(ForeignKey("exchange.id"), nullable=True)
    instrument_type_id: Mapped[int | None] = mapped_column(ForeignKey("instrument_type.id"), nullable=True)

    instrument: Mapped["Instrument | None"] = relationship()
    listing: Mapped["Listing | None"] = relationship()
    exchange: Mapped["Exchange | None"] = relationship()
    instrument_type: Mapped["InstrumentType | None"] = relationship()
