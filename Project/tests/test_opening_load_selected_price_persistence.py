from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, PriceRecord
from pokus_backend.domain.reference_models import Provider, ProviderAttempt
from pokus_backend.jobs.opening_load_worker import (
    OpeningLoadSourcePolicy,
    execute_opening_load_for_instrument_day,
)
from pokus_backend.pricing.adapter import PriceCandidateRequest
from pokus_backend.pricing.candidate_value_persistence import CandidateSetAuditEvidence
from pokus_backend.pricing.contract import PriceCandidate


class _FakeAdapter:
    def __init__(self, candidates: list[PriceCandidate]) -> None:
        self._candidates = candidates

    def fetch_current_day_open_candidates(self, request: PriceCandidateRequest) -> list[PriceCandidate]:
        return list(self._candidates)


class OpeningLoadSelectedPricePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = sa.create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.exchange = Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True)
        self.instrument_type = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
        self.provider_alpha = Provider(code="ALPHA", name="Alpha", is_active=True)
        self.provider_beta = Provider(code="BETA", name="Beta", is_active=True)
        self.session.add_all([self.exchange, self.instrument_type, self.provider_alpha, self.provider_beta])
        self.session.flush()

        self.instrument = Instrument(instrument_type_id=self.instrument_type.id, canonical_name="Example Corp")
        self.session.add(self.instrument)
        self.session.flush()

        self.listing = Listing(instrument_id=self.instrument.id, exchange_id=self.exchange.id, symbol="EXMP")
        self.session.add(self.listing)
        self.session.flush()

        self.alpha_attempt = ProviderAttempt(
            attempt_key="alpha-open-1",
            provider_id=self.provider_alpha.id,
            exchange_id=self.exchange.id,
            request_purpose="pricing",
            load_type="current_day_open",
            requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            result_status="success",
        )
        self.beta_attempt = ProviderAttempt(
            attempt_key="beta-open-1",
            provider_id=self.provider_beta.id,
            exchange_id=self.exchange.id,
            request_purpose="pricing",
            load_type="current_day_open",
            requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            result_status="success",
        )
        self.session.add_all([self.alpha_attempt, self.beta_attempt])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_selected_opening_candidate_is_persisted_as_official_price_record(self) -> None:
        request = PriceCandidateRequest(
            instrument_id=str(self.instrument.id),
            listing_id=str(self.listing.id),
            exchange="NYSE",
            symbol="EXMP",
            trading_day=date(2026, 5, 1),
        )
        audit = CandidateSetAuditEvidence(
            candidate_set_key="nyse-exmp-2026-05-01-open",
            requested_at=datetime(2026, 5, 1, 13, 31, tzinfo=timezone.utc),
            selection_inputs={"load_type": "current_day_open"},
        )
        adapter = _FakeAdapter(
            [
                PriceCandidate(
                    instrument_id=request.instrument_id,
                    listing_id=request.listing_id,
                    exchange="NYSE",
                    trading_day=request.trading_day,
                    price_type="current_day_unadjusted_open",
                    value=Decimal("100.50"),
                    currency="USD",
                    provider_code="ALPHA",
                    provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                    provider_request_id="alpha-req-1",
                    provider_metadata={"source": "alpha"},
                ),
                PriceCandidate(
                    instrument_id=request.instrument_id,
                    listing_id=request.listing_id,
                    exchange="NYSE",
                    trading_day=request.trading_day,
                    price_type="current_day_unadjusted_open",
                    value=Decimal("101.00"),
                    currency="USD",
                    provider_code="BETA",
                    provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                    provider_request_id="beta-req-1",
                    provider_metadata={"source": "beta"},
                ),
            ]
        )

        result = execute_opening_load_for_instrument_day(
            self.session,
            adapter=adapter,
            request=request,
            audit=audit,
            source_policy_by_provider={
                "ALPHA": OpeningLoadSourcePolicy(
                    reliability_score=Decimal("0.95"),
                    historical_availability_ratio=Decimal("0.80"),
                    exchange_coverage_quality=Decimal("0.80"),
                    fixed_source_order=2,
                ),
                "BETA": OpeningLoadSourcePolicy(
                    reliability_score=Decimal("0.90"),
                    historical_availability_ratio=Decimal("0.99"),
                    exchange_coverage_quality=Decimal("0.99"),
                    fixed_source_order=1,
                ),
            },
        )
        self.session.commit()

        self.assertIsNotNone(result)
        self.assertEqual(result.selection.winner.provider_code, "ALPHA")
        stored = self.session.query(PriceRecord).one()
        self.assertEqual(stored.listing_id, self.listing.id)
        self.assertEqual(stored.trading_date, date(2026, 5, 1))
        self.assertEqual(stored.price_type, "current_day_unadjusted_open")
        self.assertEqual(stored.value, Decimal("100.50000000"))
        self.assertEqual(stored.currency, "USD")

    def test_rerun_updates_existing_selected_record_without_duplicates(self) -> None:
        request = PriceCandidateRequest(
            instrument_id=str(self.instrument.id),
            listing_id=str(self.listing.id),
            exchange="NYSE",
            symbol="EXMP",
            trading_day=date(2026, 5, 1),
        )
        audit = CandidateSetAuditEvidence(
            candidate_set_key="nyse-exmp-2026-05-01-open",
            requested_at=datetime(2026, 5, 1, 13, 31, tzinfo=timezone.utc),
            selection_inputs={"load_type": "current_day_open"},
        )
        adapter = _FakeAdapter(
            [
                PriceCandidate(
                    instrument_id=request.instrument_id,
                    listing_id=request.listing_id,
                    exchange="NYSE",
                    trading_day=request.trading_day,
                    price_type="current_day_unadjusted_open",
                    value=Decimal("100.50"),
                    currency="USD",
                    provider_code="ALPHA",
                    provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                    provider_request_id="alpha-req-1",
                    provider_metadata={"source": "alpha"},
                ),
            ]
        )

        execute_opening_load_for_instrument_day(
            self.session,
            adapter=adapter,
            request=request,
            audit=audit,
            source_policy_by_provider={
                "ALPHA": OpeningLoadSourcePolicy(
                    reliability_score=Decimal("0.95"),
                    historical_availability_ratio=Decimal("0.80"),
                    exchange_coverage_quality=Decimal("0.80"),
                    fixed_source_order=2,
                )
            },
        )
        self.session.commit()

        execute_opening_load_for_instrument_day(
            self.session,
            adapter=adapter,
            request=request,
            audit=audit,
            source_policy_by_provider={
                "ALPHA": OpeningLoadSourcePolicy(
                    reliability_score=Decimal("0.95"),
                    historical_availability_ratio=Decimal("0.80"),
                    exchange_coverage_quality=Decimal("0.80"),
                    fixed_source_order=2,
                )
            },
        )
        self.session.commit()

        rows = self.session.query(PriceRecord).all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].trading_date, date(2026, 5, 1))
        self.assertEqual(rows[0].price_type, "current_day_unadjusted_open")


if __name__ == "__main__":
    unittest.main()
