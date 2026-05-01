from __future__ import annotations

import datetime as dt
import unittest

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain import (
    Base,
    Exchange,
    IdentifierRecord,
    Instrument,
    InstrumentType,
    Listing,
    SupportedUniverseState,
    SupportedUniverseStatus,
)


class InstrumentIdentityModelsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.session.add_all([self.exchange, self.instrument_type])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_instrument_and_listing_are_separate_with_foreign_keys(self) -> None:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Apple Inc.")
        self.session.add(instrument)
        self.session.commit()

        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol="AAPL")
        self.session.add(listing)
        self.session.commit()

        stored = self.session.query(Listing).one()
        self.assertEqual(stored.instrument.id, instrument.id)
        self.assertEqual(stored.exchange_id, self.exchange.id)

    def test_listing_uniqueness_boundaries_are_enforced(self) -> None:
        first = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Microsoft Corp.")
        second = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="MSFT Clone")
        self.session.add_all([first, second])
        self.session.commit()

        self.session.add(Listing(instrument_id=first.id, exchange_id=self.exchange.id, symbol="MSFT"))
        self.session.commit()

        self.session.add(Listing(instrument_id=second.id, exchange_id=self.exchange.id, symbol="MSFT"))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

        self.session.add(Listing(instrument_id=first.id, exchange_id=self.exchange.id, symbol="MSFT-2"))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_identifier_records_store_stable_provider_reference_ids(self) -> None:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Tesla, Inc.")
        self.session.add(instrument)
        self.session.commit()

        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol="TSLA")
        self.session.add(listing)
        self.session.commit()

        self.session.add(
            IdentifierRecord(
                instrument_id=instrument.id,
                listing_id=listing.id,
                provider_code="OPENFIGI",
                identifier_type="FIGI",
                identifier_value="BBG000N9MNX3",
            )
        )
        self.session.commit()

        self.session.add(
            IdentifierRecord(
                provider_code="OPENFIGI",
                identifier_type="FIGI",
                identifier_value="BBG000N9MNX3",
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_supported_universe_state_represents_required_status_values(self) -> None:
        instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp.")
        self.session.add(instrument)
        self.session.commit()

        listing = Listing(instrument_id=instrument.id, exchange_id=self.exchange.id, symbol="EXM")
        self.session.add(listing)
        self.session.commit()

        state = SupportedUniverseState(
            listing_id=listing.id,
            status=SupportedUniverseStatus.NOT_YET_SIGNAL_ELIGIBLE,
            effective_from=dt.date(2026, 5, 1),
        )
        self.session.add(state)
        self.session.commit()

        for status in (
            SupportedUniverseStatus.SUPPORTED,
            SupportedUniverseStatus.DELISTING_SUSPECTED,
            SupportedUniverseStatus.REMOVED,
            SupportedUniverseStatus.HISTORICAL_ONLY,
        ):
            state.status = status
            self.session.commit()

        stored = self.session.query(SupportedUniverseState).one()
        self.assertEqual(stored.status, SupportedUniverseStatus.HISTORICAL_ONLY)


if __name__ == "__main__":
    unittest.main()
