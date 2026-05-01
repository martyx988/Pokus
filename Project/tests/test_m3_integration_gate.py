from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
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
from pokus_backend.domain.reference_models import (
    Provider,
    ProviderAttempt,
    ProviderExchangeReliabilityScore,
    ValidationExchangeReport,
    ValidationRun,
)
from pokus_backend.pricing.reliability_scores import ReliabilityOutcomeWindow, update_provider_exchange_reliability_score
from pokus_backend.pricing.source_prioritization import SourcePrioritizationCandidate, select_source_candidate
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


class Milestone3IntegrationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True, activity_priority_rank=1),
                Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True, activity_priority_rank=2),
                Exchange(code="PSE", name="Prague Stock Exchange", is_launch_active=True, activity_priority_rank=3),
                InstrumentType(code="STOCK", name="Stock", is_launch_active=True),
                Provider(code="ALPHA", name="Alpha", is_active=True),
                Provider(code="BETA", name="Beta", is_active=True),
            ]
        )
        self.session.flush()

        self.exchange_by_code = {row.code: row for row in self.session.query(Exchange).all()}
        self.provider_by_code = {row.code: row for row in self.session.query(Provider).all()}
        self.instrument_type_id = self.session.query(InstrumentType).filter_by(code="STOCK").one().id

        self.nyse_listing = self._create_supported_listing("NYSE", "ALP")
        self.nasdaq_listing = self._create_supported_listing("NASDAQ", "BET")
        self.pse_listing = self._create_supported_listing("PSE", "CEZ")

        self._seed_pass_fixture_for_exchange("NYSE", self.nyse_listing.id)
        self._seed_pass_fixture_for_exchange("NASDAQ", self.nasdaq_listing.id)
        self._seed_pse_failing_fixture(self.pse_listing.id)
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_m3_integration_gate_reports_full_evidence_and_blocks_pse_on_fixture_failure(self) -> None:
        result = orchestrate_launch_exchange_validation_run(
            self.session,
            target_exchange_codes=["NYSE", "NASDAQ", "PSE"],
            run_key="m3-gate",
        )
        self.session.commit()

        self.assertEqual(result.run.state, "succeeded")

        reports = {
            report.exchange.code: report
            for report in self.session.query(ValidationExchangeReport)
            .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
            .join(Exchange, Exchange.id == ValidationExchangeReport.exchange_id)
            .filter(ValidationRun.run_key == "m3-gate")
            .all()
        }

        self.assertSetEqual(set(reports.keys()), {"NYSE", "NASDAQ", "PSE"})
        for report in reports.values():
            self.assertIn("discovery_listing", report.result_buckets)
            self.assertIn("completeness_timeliness", report.result_buckets)
            self.assertIn("disagreement_benchmark", report.result_buckets)
            self.assertIn("calendar_validation", report.result_buckets)
            self.assertIn(report.result_buckets["discovery_listing"]["status"], {"pass", "fail"})
            self.assertIn(report.result_buckets["completeness_timeliness"]["status"], {"pass", "fail"})
            self.assertIn(report.result_buckets["disagreement_benchmark"]["status"], {"pass", "fail"})
            self.assertIn(report.result_buckets["calendar_validation"]["status"], {"pass", "fail"})

        # Provider attempt retention evidence
        self.assertGreaterEqual(self.session.query(ProviderAttempt).count(), 6)

        # Candidate-value and source-prioritization reproducibility evidence
        winner = select_source_candidate(
            [
                SourcePrioritizationCandidate(
                    candidate_key="nyse-alpha",
                    provider_code="ALPHA",
                    value=Decimal("100.00"),
                    reliability_score=Decimal("0.97"),
                    historical_availability_ratio=Decimal("0.95"),
                    exchange_coverage_quality=Decimal("0.95"),
                    fixed_source_order=2,
                ),
                SourcePrioritizationCandidate(
                    candidate_key="nyse-beta",
                    provider_code="BETA",
                    value=Decimal("100.00"),
                    reliability_score=Decimal("0.90"),
                    historical_availability_ratio=Decimal("0.99"),
                    exchange_coverage_quality=Decimal("0.99"),
                    fixed_source_order=1,
                ),
            ]
        )
        self.assertEqual(winner.evidence.winner_reason, "provider_exchange_reliability_score")

        # Reliability-score update evidence
        nyse_alpha_score = self.session.query(ProviderExchangeReliabilityScore).join(Exchange).join(Provider).filter(
            Exchange.code == "NYSE", Provider.code == "ALPHA"
        ).one_or_none()
        self.assertIsNotNone(nyse_alpha_score)

        # PSE failing fixture must block launch validation with actionable findings
        pse_report = reports["PSE"]
        self.assertEqual(pse_report.final_verdict, "blocked")
        self.assertIsNotNone(pse_report.findings_summary)
        self.assertIn("PSE", pse_report.findings_summary)
        self.assertIn("must remain in launch scope", pse_report.findings_summary)
        self.assertIn("calendar_library_reference_mismatch_detected", pse_report.findings_summary)

    def _create_supported_listing(self, exchange_code: str, symbol: str) -> Listing:
        exchange_id = self.exchange_by_code[exchange_code].id
        instrument = Instrument(instrument_type_id=self.instrument_type_id, canonical_name=f"Instrument {symbol}")
        self.session.add(instrument)
        self.session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=exchange_id, symbol=symbol)
        self.session.add(listing)
        self.session.flush()
        self.session.add(SupportedUniverseState(listing_id=listing.id, status=SupportedUniverseStatus.SUPPORTED))
        self.session.flush()
        return listing

    def _seed_pass_fixture_for_exchange(self, exchange_code: str, listing_id: int) -> None:
        exchange = self.exchange_by_code[exchange_code]
        alpha = self.provider_by_code["ALPHA"]
        beta = self.provider_by_code["BETA"]

        attempt_a = self._add_attempt(exchange.id, alpha.id, f"{exchange_code.lower()}-alpha-attempt", latency_ms=60_000)
        attempt_b = self._add_attempt(exchange.id, beta.id, f"{exchange_code.lower()}-beta-attempt", latency_ms=70_000)

        self._add_candidate(
            listing_id=listing_id,
            provider_id=alpha.id,
            provider_attempt_id=attempt_a.id,
            candidate_key=f"{exchange_code.lower()}-open-a",
            trading_day=date(2026, 5, 1),
            price_type="current_day_unadjusted_open",
            value=Decimal("100"),
            benchmark=Decimal("100"),
            expected_is_trading_day=True,
            reference_type="weekday",
        )
        self._add_candidate(
            listing_id=listing_id,
            provider_id=beta.id,
            provider_attempt_id=attempt_b.id,
            candidate_key=f"{exchange_code.lower()}-open-b",
            trading_day=date(2026, 5, 1),
            price_type="current_day_unadjusted_open",
            value=Decimal("100"),
            benchmark=Decimal("100"),
            expected_is_trading_day=True,
            reference_type="weekday",
        )
        self._add_candidate(
            listing_id=listing_id,
            provider_id=alpha.id,
            provider_attempt_id=attempt_a.id,
            candidate_key=f"{exchange_code.lower()}-close-a",
            trading_day=date(2026, 4, 30),
            price_type="historical_adjusted_close",
            value=Decimal("99"),
            benchmark=None,
            expected_is_trading_day=None,
            reference_type=None,
        )

        update_provider_exchange_reliability_score(
            self.session,
            provider_code="ALPHA",
            exchange_code=exchange_code,
            outcome=ReliabilityOutcomeWindow(
                window_key=f"{exchange_code.lower()}-window",
                benchmark_match_rate=Decimal("0.98"),
                missing_rate=Decimal("0.01"),
                timeliness_rate=Decimal("0.98"),
                stale_data_rate=Decimal("0.0"),
                provider_error_rate=Decimal("0.0"),
                disagreement_rate=Decimal("0.01"),
                observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            ),
        )

    def _seed_pse_failing_fixture(self, listing_id: int) -> None:
        exchange = self.exchange_by_code["PSE"]
        alpha = self.provider_by_code["ALPHA"]
        beta = self.provider_by_code["BETA"]

        attempt_a = self._add_attempt(exchange.id, alpha.id, "pse-alpha-attempt", latency_ms=35 * 60 * 1000)
        attempt_b = self._add_attempt(exchange.id, beta.id, "pse-beta-attempt", latency_ms=35 * 60 * 1000)

        # Daily candidates disagree with benchmark and have mismatched calendar reference for explicit failure evidence.
        self._add_candidate(
            listing_id=listing_id,
            provider_id=alpha.id,
            provider_attempt_id=attempt_a.id,
            candidate_key="pse-open-a",
            trading_day=date(2026, 5, 4),
            price_type="current_day_unadjusted_open",
            value=Decimal("95"),
            benchmark=Decimal("100"),
            expected_is_trading_day=False,
            reference_type="holiday",
        )
        self._add_candidate(
            listing_id=listing_id,
            provider_id=beta.id,
            provider_attempt_id=attempt_b.id,
            candidate_key="pse-open-b",
            trading_day=date(2026, 5, 4),
            price_type="current_day_unadjusted_open",
            value=Decimal("94"),
            benchmark=Decimal("100"),
            expected_is_trading_day=False,
            reference_type="holiday",
        )

    def _add_attempt(self, exchange_id: int, provider_id: int, attempt_key: str, *, latency_ms: int) -> ProviderAttempt:
        attempt = ProviderAttempt(
            attempt_key=attempt_key,
            provider_id=provider_id,
            exchange_id=exchange_id,
            request_purpose="pricing",
            load_type="current_day_open",
            requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            latency_ms=latency_ms,
            result_status="success",
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def _add_candidate(
        self,
        *,
        listing_id: int,
        provider_id: int,
        provider_attempt_id: int,
        candidate_key: str,
        trading_day: date,
        price_type: str,
        value: Decimal,
        benchmark: Decimal | None,
        expected_is_trading_day: bool | None,
        reference_type: str | None,
    ) -> None:
        selection_inputs: dict[str, object] = {}
        if benchmark is not None:
            selection_inputs["benchmark_value"] = str(benchmark)
        if expected_is_trading_day is not None:
            selection_inputs["calendar_reference"] = {
                "expected_is_trading_day": expected_is_trading_day,
                "reference_type": reference_type,
                "reference_source": "official_exchange_calendar",
            }

        self.session.add(
            CandidatePriceValue(
                candidate_key=candidate_key,
                candidate_set_key=f"set-{candidate_key}",
                listing_id=listing_id,
                provider_id=provider_id,
                provider_attempt_id=provider_attempt_id,
                trading_date=trading_day,
                price_type=price_type,
                value=value,
                currency="USD",
                provider_request_id=f"req-{candidate_key}",
                provider_observed_at=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
                audit_metadata={"selection_inputs": selection_inputs},
            )
        )


if __name__ == "__main__":
    unittest.main()
