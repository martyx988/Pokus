from __future__ import annotations

import datetime as dt
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain import (
    Base,
    Exchange,
    Instrument,
    InstrumentType,
    Listing,
)
from pokus_backend.domain.universe_change_models import UniverseChangeEventType, UniverseChangeRecord


class UniverseChangeRecordModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        event.listen(self.engine, "connect", lambda dbapi_connection, _: dbapi_connection.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(
            self.engine,
            tables=[
                Exchange.__table__,
                InstrumentType.__table__,
                Instrument.__table__,
                Listing.__table__,
                UniverseChangeRecord.__table__,
            ],
        )
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.session.add_all([self.exchange, self.instrument_type])
        self.session.commit()

        self.instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp.")
        self.session.add(self.instrument)
        self.session.commit()

        self.listing = Listing(
            instrument_id=self.instrument.id,
            exchange_id=self.exchange.id,
            symbol="EXM",
        )
        self.session.add(self.listing)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_required_event_types_are_representable(self) -> None:
        for event_type in UniverseChangeEventType:
            self.session.add(
                UniverseChangeRecord(
                    event_type=event_type,
                    effective_day=dt.date(2026, 5, 1),
                    reason="Universe lifecycle update",
                    details="Captured for audit history",
                    old_state_evidence={"status": "supported"},
                    new_state_evidence={"status": "removed"},
                )
            )
        self.session.commit()

        self.assertEqual(self.session.query(UniverseChangeRecord).count(), len(UniverseChangeEventType))

    def test_reason_is_required_and_nonempty(self) -> None:
        self.session.add(
            UniverseChangeRecord(
                event_type=UniverseChangeEventType.EXCLUDED,
                effective_day=dt.date(2026, 5, 1),
                reason=None,  # type: ignore[arg-type]
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        self.session.add(
            UniverseChangeRecord(
                event_type=UniverseChangeEventType.EXCLUDED,
                effective_day=dt.date(2026, 5, 1),
                reason="   ",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_record_can_reference_instrument_listing_exchange_and_type_context(self) -> None:
        record = UniverseChangeRecord(
            event_type=UniverseChangeEventType.SYMBOL_CHANGED,
            effective_day=dt.date(2026, 5, 1),
            reason="Issuer changed ticker after merger.",
            instrument_id=self.instrument.id,
            listing_id=self.listing.id,
            exchange_id=self.exchange.id,
            instrument_type_id=self.instrument_type.id,
            old_state_evidence={"symbol": "OLD"},
            new_state_evidence={"symbol": "NEW"},
        )
        self.session.add(record)
        self.session.commit()

        stored = self.session.query(UniverseChangeRecord).one()
        self.assertEqual(stored.instrument_id, self.instrument.id)
        self.assertEqual(stored.listing_id, self.listing.id)
        self.assertEqual(stored.exchange_id, self.exchange.id)
        self.assertEqual(stored.instrument_type_id, self.instrument_type.id)

    def test_reference_integrity_is_enforced(self) -> None:
        self.session.add(
            UniverseChangeRecord(
                event_type=UniverseChangeEventType.REMOVED,
                effective_day=dt.date(2026, 5, 1),
                reason="Listing no longer in selected scope.",
                listing_id=999999,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()


if __name__ == "__main__":
    unittest.main()
