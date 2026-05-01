from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.discovery.supported_universe import project_supported_universe_state
from pokus_backend.domain import (
    Base,
    Exchange,
    Instrument,
    InstrumentType,
    Listing,
    SupportedUniverseState,
    SupportedUniverseStatus,
    UniverseChangeRecord,
)
from pokus_backend.domain.universe_change_models import UniverseChangeEventType


class SupportedUniverseProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                Exchange(code="XNAS", name="Nasdaq", is_launch_active=True),
                Exchange(code="XPRA", name="Prague Stock Exchange", is_launch_active=False),
                InstrumentType(code="STOCK", name="Stock", is_launch_active=True),
                InstrumentType(code="ETF", name="ETF", is_launch_active=False),
            ]
        )
        self.session.flush()

        self.nyse_id = self.session.scalar(select(Exchange.id).where(Exchange.code == "NYSE"))
        self.xnas_id = self.session.scalar(select(Exchange.id).where(Exchange.code == "XNAS"))
        self.xpra_id = self.session.scalar(select(Exchange.id).where(Exchange.code == "XPRA"))
        self.stock_id = self.session.scalar(select(InstrumentType.id).where(InstrumentType.code == "STOCK"))
        self.etf_id = self.session.scalar(select(InstrumentType.id).where(InstrumentType.code == "ETF"))

        stock_a = Instrument(instrument_type_id=self.stock_id, canonical_name="Instrument A")
        stock_b = Instrument(instrument_type_id=self.stock_id, canonical_name="Instrument B")
        etf_c = Instrument(instrument_type_id=self.etf_id, canonical_name="Instrument C")
        self.session.add_all([stock_a, stock_b, etf_c])
        self.session.flush()

        self.a_nyse = Listing(instrument_id=stock_a.id, exchange_id=self.nyse_id, symbol="A.N")
        self.a_xnas = Listing(instrument_id=stock_a.id, exchange_id=self.xnas_id, symbol="A.Q")
        self.b_nyse = Listing(instrument_id=stock_b.id, exchange_id=self.nyse_id, symbol="B.N")
        self.c_xpra = Listing(instrument_id=etf_c.id, exchange_id=self.xpra_id, symbol="C.P")
        self.session.add_all([self.a_nyse, self.a_xnas, self.b_nyse, self.c_xpra])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_projection_marks_only_selected_scoped_listings_supported(self) -> None:
        result = project_supported_universe_state(
            self.session,
            selected_listing_ids=[self.a_xnas.id, self.b_nyse.id, self.c_xpra.id],
            supported_exchange_codes=["NYSE", "XNAS"],
            supported_instrument_type_codes=["STOCK"],
            effective_day=date(2026, 2, 1),
        )
        self.session.commit()

        states = self.session.scalars(select(SupportedUniverseState).order_by(SupportedUniverseState.listing_id)).all()
        self.assertEqual(result.supported_listing_ids, (self.a_xnas.id, self.b_nyse.id))
        self.assertEqual([state.listing_id for state in states], [self.a_xnas.id, self.b_nyse.id])
        events = self.session.scalars(select(UniverseChangeRecord).order_by(UniverseChangeRecord.id.asc())).all()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, UniverseChangeEventType.ADDED)
        self.assertEqual(events[1].event_type, UniverseChangeEventType.ADDED)

    def test_projection_records_restored_excluded_degraded_and_removed_events(self) -> None:
        self.session.add_all(
            [
                SupportedUniverseState(listing_id=self.a_nyse.id, status=SupportedUniverseStatus.DELISTING_SUSPECTED),
                SupportedUniverseState(listing_id=self.a_xnas.id, status=SupportedUniverseStatus.SUPPORTED),
                SupportedUniverseState(listing_id=self.b_nyse.id, status=SupportedUniverseStatus.HISTORICAL_ONLY),
            ]
        )
        self.session.commit()

        project_supported_universe_state(
            self.session,
            selected_listing_ids=[self.a_nyse.id],
            supported_exchange_codes=["NYSE", "XNAS"],
            supported_instrument_type_codes=["STOCK"],
            effective_day=date(2026, 2, 2),
        )
        self.session.commit()

        events = self.session.scalars(select(UniverseChangeRecord).order_by(UniverseChangeRecord.id.asc())).all()
        event_types = [event.event_type for event in events]
        self.assertIn(UniverseChangeEventType.RESTORED, event_types)
        self.assertIn(UniverseChangeEventType.EXCLUDED, event_types)
        self.assertIn(UniverseChangeEventType.DEGRADED, event_types)
        self.assertGreaterEqual(event_types.count(UniverseChangeEventType.REMOVED), 2)
        for event in events:
            self.assertIsNotNone(event.effective_day)
            self.assertIsNotNone(event.reason)
            self.assertIsNotNone(event.details)
            self.assertIsNotNone(event.old_state_evidence)
            self.assertIsNotNone(event.new_state_evidence)
            self.assertIsNotNone(event.instrument_id)
            self.assertIsNotNone(event.exchange_id)
            self.assertIsNotNone(event.instrument_type_id)

    def test_projection_rejects_multiple_selected_listings_for_same_instrument(self) -> None:
        with self.assertRaises(ValueError):
            project_supported_universe_state(
                self.session,
                selected_listing_ids=[self.a_nyse.id, self.a_xnas.id],
                supported_exchange_codes=["NYSE", "XNAS"],
                supported_instrument_type_codes=["STOCK"],
            )


if __name__ == "__main__":
    unittest.main()
