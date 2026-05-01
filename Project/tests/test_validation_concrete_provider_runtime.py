from __future__ import annotations

import os
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.domain import (
    Base,
    CandidatePriceValue,
    Exchange,
    Instrument,
    InstrumentType,
    Listing,
    SupportedUniverseState,
    SupportedUniverseStatus,
)
from pokus_backend.domain.reference_models import ProviderAttempt
from pokus_backend.validation.concrete_provider_runtime import ConcreteValidationRuntimeRequest
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class ConcreteProviderRuntimeValidationTests(unittest.TestCase):
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
        self.session.flush()
        instrument_type_id = self.session.scalar(select(InstrumentType.id).where(InstrumentType.code == "STOCK"))
        assert instrument_type_id is not None
        instrument = Instrument(instrument_type_id=instrument_type_id, canonical_name="Apple Inc")
        self.session.add(instrument)
        self.session.flush()
        nyse_id = self.session.scalar(select(Exchange.id).where(Exchange.code == "NYSE"))
        assert nyse_id is not None
        self.listing = Listing(instrument_id=instrument.id, exchange_id=nyse_id, symbol="AAPL")
        self.session.add(self.listing)
        self.session.flush()
        self.session.add(SupportedUniverseState(listing_id=self.listing.id, status=SupportedUniverseStatus.SUPPORTED))
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_orchestrator_persists_provider_attempt_and_candidate_evidence_from_live_provider(self) -> None:
        if os.getenv("RUN_CONCRETE_PROVIDER_TEST") != "1":
            self.skipTest("set RUN_CONCRETE_PROVIDER_TEST=1 to enable live provider runtime test")

        result = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE"],
            run_key="live-provider-path",
            concrete_runtime_requests=[
                ConcreteValidationRuntimeRequest(exchange_code="NYSE", listing_id=self.listing.id, symbol="AAPL.US")
            ],
        )
        self.session.commit()

        self.assertEqual(result.run.state, "succeeded")

        attempts = self.session.execute(select(ProviderAttempt).where(ProviderAttempt.request_purpose == "validation_runtime")).scalars().all()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0].result_status, "success")
        self.assertEqual(attempts[0].exchange.code, "NYSE")

        candidates = self.session.execute(select(CandidatePriceValue).where(CandidatePriceValue.listing_id == self.listing.id)).scalars().all()
        self.assertEqual(len(candidates), 2)
        self.assertSetEqual({row.price_type for row in candidates}, {"current_day_unadjusted_open", "historical_adjusted_close"})
        self.assertTrue(all(row.provider_attempt_id is not None for row in candidates))


if __name__ == "__main__":
    unittest.main()
