from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.discovery.persistence import persist_discovery_candidates
from pokus_backend.domain import Base, Exchange, IdentifierRecord, InstrumentType, Listing, UniverseChangeRecord
from pokus_backend.domain.universe_change_models import UniverseChangeEventType


class DiscoveryCandidatePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                InstrumentType(code="STOCK", name="Stock", is_launch_active=True),
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_repeated_ingest_is_idempotent_for_listing_and_instrument(self) -> None:
        candidate = DiscoveryCandidate(
            exchange="NYSE",
            instrument_type="STOCK",
            symbol="AAPL",
            name="Apple Inc.",
            stable_identifiers={},
        )

        first = persist_discovery_candidates(self.session, [candidate], provider_code="openfigi")
        self.session.commit()
        second = persist_discovery_candidates(self.session, [candidate], provider_code="openfigi")
        self.session.commit()

        self.assertEqual(first.listing_ids, second.listing_ids)
        self.assertEqual(self.session.query(Listing).count(), 1)
        self.assertEqual(len(set(second.listing_ids)), 1)

    def test_identifier_capture_and_continuity_update(self) -> None:
        initial = DiscoveryCandidate(
            exchange="NYSE",
            instrument_type="STOCK",
            symbol="AAPL",
            name="Apple Inc.",
            stable_identifiers={"figi": "BBG000B9XRY4"},
        )
        updated = DiscoveryCandidate(
            exchange="NYSE",
            instrument_type="STOCK",
            symbol="AAPL",
            name="Apple Incorporated",
            stable_identifiers={"figi": "BBG000B9XRY9", "isin": "US0378331005"},
        )

        persist_discovery_candidates(
            self.session,
            [initial],
            provider_code="openfigi",
            effective_day=date(2026, 1, 10),
        )
        self.session.commit()
        persist_discovery_candidates(
            self.session,
            [updated],
            provider_code="openfigi",
            effective_day=date(2026, 1, 11),
        )
        self.session.commit()

        listing_id = self.session.scalar(select(Listing.id))
        records = self.session.scalars(
            select(IdentifierRecord)
            .where(IdentifierRecord.listing_id == listing_id)
            .order_by(IdentifierRecord.identifier_type.asc())
        ).all()

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].identifier_type, "FIGI")
        self.assertEqual(records[0].identifier_value, "BBG000B9XRY9")
        self.assertEqual(records[0].provider_code, "OPENFIGI")
        self.assertEqual(records[1].identifier_type, "ISIN")
        self.assertEqual(records[1].identifier_value, "US0378331005")

        events = self.session.scalars(
            select(UniverseChangeRecord).order_by(UniverseChangeRecord.id.asc())
        ).all()
        self.assertEqual(events[0].event_type, UniverseChangeEventType.ADDED)
        self.assertEqual(events[1].event_type, UniverseChangeEventType.NAME_CHANGED)
        self.assertEqual(events[2].event_type, UniverseChangeEventType.IDENTIFIER_CHANGED)
        for event in events:
            self.assertIsNotNone(event.effective_day)
            self.assertIsNotNone(event.reason)
            self.assertIsNotNone(event.instrument_id)
            self.assertIsNotNone(event.exchange_id)
            self.assertIsNotNone(event.instrument_type_id)
            self.assertIsNotNone(event.old_state_evidence if event.event_type != UniverseChangeEventType.ADDED else {})
            self.assertIsNotNone(event.new_state_evidence)


if __name__ == "__main__":
    unittest.main()
