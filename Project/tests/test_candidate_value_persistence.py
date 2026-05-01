from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, CandidatePriceValue, Exchange, Instrument, InstrumentType, Listing
from pokus_backend.domain.reference_models import Provider, ProviderAttempt
from pokus_backend.pricing.candidate_value_persistence import (
    CandidateSetAuditEvidence,
    persist_candidate_price_values,
)
from pokus_backend.pricing.contract import PriceCandidate


class CandidateValuePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.provider = Provider(code="ALPHA", name="Alpha", is_active=True)
        self.session.add_all([self.exchange, self.instrument_type, self.provider])
        self.session.flush()
        self.instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp.")
        self.session.add(self.instrument)
        self.session.flush()
        self.listing = Listing(instrument_id=self.instrument.id, exchange_id=self.exchange.id, symbol="EXMP")
        self.session.add(self.listing)
        self.session.flush()
        self.attempt = ProviderAttempt(
            attempt_key="alpha-nyse-open-1",
            provider_id=self.provider.id,
            exchange_id=self.exchange.id,
            request_purpose="pricing",
            load_type="current_day_open",
            requested_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            result_status="success",
        )
        self.session.add(self.attempt)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_repeated_identical_set_is_deduplicated(self) -> None:
        candidate = PriceCandidate(
            instrument_id="instrument-1",
            listing_id=str(self.listing.id),
            exchange="NYSE",
            trading_day=date(2026, 5, 1),
            price_type="current_day_unadjusted_open",
            value=Decimal("102.75000000"),
            currency="USD",
            provider_code="ALPHA",
            provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            provider_request_id="req-1",
            provider_metadata={"raw_symbol": "EXMP"},
        )
        audit = CandidateSetAuditEvidence(
            candidate_set_key="nyse-2026-05-01-open-alpha",
            requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            provider_attempt_key=self.attempt.attempt_key,
            selection_inputs={"load_type": "current_day_open"},
        )

        first = persist_candidate_price_values(self.session, candidates=[candidate], audit=audit)
        self.session.commit()
        second = persist_candidate_price_values(self.session, candidates=[candidate], audit=audit)
        self.session.commit()

        self.assertEqual(first[0].candidate_key, second[0].candidate_key)
        self.assertEqual(self.session.query(CandidatePriceValue).count(), 1)

    def test_persists_required_audit_fields(self) -> None:
        candidate = PriceCandidate(
            instrument_id="instrument-1",
            listing_id=str(self.listing.id),
            exchange="NYSE",
            trading_day=date(2026, 4, 30),
            price_type="historical_adjusted_close",
            value=Decimal("99.25000000"),
            currency="USD",
            provider_code="ALPHA",
            provider_observed_at=datetime(2026, 4, 30, 20, 0, tzinfo=timezone.utc),
            provider_request_id="req-2",
            provider_metadata={"vendor": "alpha"},
        )
        audit = CandidateSetAuditEvidence(
            candidate_set_key="nyse-2026-04-30-close-alpha",
            requested_at=datetime(2026, 4, 30, 20, 5, tzinfo=timezone.utc),
            provider_attempt_key=self.attempt.attempt_key,
            selection_inputs={"request_purpose": "pricing"},
        )

        persisted = persist_candidate_price_values(self.session, candidates=[candidate], audit=audit)[0]
        self.session.commit()

        self.assertEqual(persisted.candidate_set_key, "nyse-2026-04-30-close-alpha")
        self.assertEqual(persisted.provider_id, self.provider.id)
        self.assertEqual(persisted.provider_attempt_id, self.attempt.id)
        self.assertEqual(persisted.price_type, "historical_adjusted_close")
        self.assertEqual(persisted.currency, "USD")
        self.assertEqual(persisted.value, Decimal("99.25000000"))
        self.assertEqual(persisted.audit_metadata["provider_metadata"], {"vendor": "alpha"})
        self.assertEqual(persisted.audit_metadata["selection_inputs"], {"request_purpose": "pricing"})
        self.assertEqual(persisted.provider_request_id, "req-2")
        self.assertIsNotNone(persisted.provider_observed_at)


if __name__ == "__main__":
    unittest.main()
