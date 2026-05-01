from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sqlalchemy as sa
from sqlalchemy.orm import Session

from pokus_backend import api
from pokus_backend.calendars.result import TradingDayDecision, TradingDayStatus
from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing, PriceRecord
from pokus_backend.domain.instrument_models import CandidatePriceValue, SupportedUniverseState, SupportedUniverseStatus
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import PublicationRecord, QualityCheck
from pokus_backend.domain.reference_models import Provider, ProviderAttempt, ValidationExchangeReport, ValidationRun
from pokus_backend.jobs.opening_load_outcomes import (
    OpeningLoadOutcomeInput,
    classify_opening_load_outcome,
    decide_and_persist_opening_publication_status,
    evaluate_and_persist_opening_correctness_validation,
    upsert_opening_load_outcome,
)
from pokus_backend.jobs.opening_load_scheduler import schedule_today_opening_load_jobs
from pokus_backend.settings import Settings
from pokus_backend.validation.run_orchestrator import orchestrate_launch_exchange_validation_run


TRADING_DATE = date(2026, 5, 1)


class Milestone4IntegrationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "m4-integration-gate.sqlite3"
        cls._db_url = f"sqlite+pysqlite:///{cls._db_path.as_posix()}"

        engine = sa.create_engine(cls._db_url)
        cls._create_dependency_tables()
        Base.metadata.create_all(
            engine,
            tables=[
                Base.metadata.tables["load_jobs"],
                Exchange.__table__,
                InstrumentType.__table__,
                Instrument.__table__,
                Listing.__table__,
                SupportedUniverseState.__table__,
                ExchangeDayLoad.__table__,
                Base.metadata.tables["instrument_load_outcome"],
                PublicationRecord.__table__,
                QualityCheck.__table__,
                PriceRecord.__table__,
                Provider.__table__,
                ProviderAttempt.__table__,
                CandidatePriceValue.__table__,
                ValidationRun.__table__,
                ValidationExchangeReport.__table__,
            ],
        )

        with Session(engine) as session:
            cls.stock = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
            session.add(cls.stock)
            session.flush()

            cls.exchanges = {
                "NYSE": Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                "NASDAQ": Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True),
                "PSE": Exchange(code="PSE", name="Prague Stock Exchange", is_launch_active=True),
                "AMEX": Exchange(code="AMEX", name="American Stock Exchange", is_launch_active=False),
            }
            session.add_all(cls.exchanges.values())

            cls.provider = Provider(code="ALPHA", name="Alpha", is_active=True)
            session.add(cls.provider)
            session.flush()

            cls.nyse_listing = cls._create_listing(session, exchange=cls.exchanges["NYSE"], symbol="NYSA")
            cls.nasdaq_primary_listing = cls._create_listing(session, exchange=cls.exchanges["NASDAQ"], symbol="NQDA")
            cls.nasdaq_failed_listing = cls._create_listing(session, exchange=cls.exchanges["NASDAQ"], symbol="NQDB")
            cls.amex_listing = cls._create_listing(session, exchange=cls.exchanges["AMEX"], symbol="AMEX")
            cls.pse_listing = cls._create_listing(session, exchange=cls.exchanges["PSE"], symbol="PSEA")

            trading_date = TRADING_DATE
            schedule_result = schedule_today_opening_load_jobs(
                session,
                today=trading_date,
                calendar_service=_GateCalendarService(),
            )
            assert schedule_result.skipped_market_closed_count == 1

            nyse_load = cls._create_load(
                session,
                exchange=cls.exchanges["NYSE"],
                trading_date=trading_date,
                eligible_count=1,
            )
            nasdaq_load = cls._create_load(
                session,
                exchange=cls.exchanges["NASDAQ"],
                trading_date=trading_date,
                eligible_count=2,
            )
            cls._seed_ready_publication(
                session,
                exchange_day_load=nyse_load,
                listing=cls.nyse_listing,
            )
            cls._seed_partial_publication(
                session,
                exchange_day_load=nasdaq_load,
                primary_listing=cls.nasdaq_primary_listing,
                failed_listing=cls.nasdaq_failed_listing,
            )
            cls._seed_market_closed_publication(
                session,
                exchange=cls.exchanges["PSE"],
                trading_date=trading_date,
            )
            cls._seed_correctness_blocked_publication(
                session,
                exchange=cls.exchanges["AMEX"],
                listing=cls.amex_listing,
                trading_date=trading_date,
            )
            cls._seed_timeliness_validation_fixture(
                session,
                exchange=cls.exchanges["NYSE"],
                listing=cls.nyse_listing,
            )
            session.commit()

        engine.dispose()

        cls.settings = Settings(
            environment="test",
            database_url=cls._db_url,
            api_host="127.0.0.1",
            api_port=0,
            worker_poll_seconds=1.0,
            app_read_token="app-token",
            operator_session_token="operator-token",
            admin_session_token="admin-token",
        )
        cls._original_load_settings = api.load_settings
        api.load_settings = lambda: cls.settings
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), api.HealthHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        api.load_settings = cls._original_load_settings
        cls._tmp_dir.cleanup()

    @classmethod
    def _create_dependency_tables(cls) -> None:
        metadata = Base.metadata
        if "load_jobs" not in metadata.tables:
            sa.Table(
                "load_jobs",
                metadata,
                sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
                sa.Column("idempotency_key", sa.Text(), nullable=True),
                sa.Column("state", sa.Text(), nullable=True),
                sa.Column("lock_token", sa.Text(), nullable=True),
                sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not any(index.name == "uq_load_jobs_active_idempotency" for index in metadata.tables["load_jobs"].indexes):
            sa.Index(
                "uq_load_jobs_active_idempotency",
                metadata.tables["load_jobs"].c.idempotency_key,
                unique=True,
                sqlite_where=sa.text("state NOT IN ('succeeded','failed','cancelled')"),
            )

    @classmethod
    def _create_listing(cls, session: Session, *, exchange: Exchange, symbol: str) -> Listing:
        instrument = Instrument(instrument_type_id=cls.stock.id, canonical_name=f"{symbol} Corp")
        session.add(instrument)
        session.flush()
        listing = Listing(instrument_id=instrument.id, exchange_id=exchange.id, symbol=symbol)
        session.add(listing)
        session.flush()
        session.add(SupportedUniverseState(listing_id=listing.id, status=SupportedUniverseStatus.SUPPORTED))
        session.flush()
        return listing

    @staticmethod
    def _create_load(
        session: Session,
        *,
        exchange: Exchange,
        trading_date: date,
        eligible_count: int,
        status: str = "not_started",
    ) -> ExchangeDayLoad:
        result = session.execute(
            sa.insert(ExchangeDayLoad.__table__).values(
                exchange_id=exchange.id,
                job_id=None,
                trading_date=trading_date,
                load_type="daily_open",
                status=status,
                eligible_instrument_count=eligible_count,
                succeeded_count=0,
                failed_count=0,
                started_at=None,
                completed_at=None,
                duration_seconds=None,
            )
        )
        load_id = int(result.inserted_primary_key[0])
        load = session.get(ExchangeDayLoad, load_id)
        if load is None:
            raise AssertionError("failed to load exchange_day_load after insert")
        return load

    @classmethod
    def _seed_ready_publication(
        cls,
        session: Session,
        *,
        exchange_day_load: ExchangeDayLoad,
        listing: Listing,
    ) -> None:
        exchange_day_load.eligible_instrument_count = 1
        session.flush()

        classification = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=exchange_day_load.id,
            listing_id=listing.id,
            job_id=None,
            classification=classification,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        session.add(
            PriceRecord(
                listing_id=listing.id,
                trading_date=exchange_day_load.trading_date,
                price_type="current_day_unadjusted_open",
                value=Decimal("123.45"),
                currency="USD",
            )
        )
        evaluate_and_persist_opening_correctness_validation(
            session,
            exchange_day_load_id=exchange_day_load.id,
            benchmark_compared_count=20,
            benchmark_mismatch_count=0,
            checked_at=datetime(2026, 5, 1, 14, 5, tzinfo=UTC),
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=exchange_day_load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @classmethod
    def _seed_partial_publication(
        cls,
        session: Session,
        *,
        exchange_day_load: ExchangeDayLoad,
        primary_listing: Listing,
        failed_listing: Listing,
    ) -> None:
        exchange_day_load.eligible_instrument_count = 2
        session.flush()

        success = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        stale = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, stale=True))
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=exchange_day_load.id,
            listing_id=primary_listing.id,
            job_id=None,
            classification=success,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=exchange_day_load.id,
            listing_id=failed_listing.id,
            job_id=None,
            classification=stale,
            occurred_at=datetime(2026, 5, 1, 14, 3, tzinfo=UTC),
        )
        session.add(
            PriceRecord(
                listing_id=primary_listing.id,
                trading_date=exchange_day_load.trading_date,
                price_type="current_day_unadjusted_open",
                value=Decimal("111.11"),
                currency="USD",
            )
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=exchange_day_load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @classmethod
    def _seed_market_closed_publication(
        cls,
        session: Session,
        *,
        exchange: Exchange,
        trading_date: date,
    ) -> None:
        load = cls._create_load(session, exchange=exchange, trading_date=trading_date, eligible_count=0, status="market_closed")
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @classmethod
    def _seed_correctness_blocked_publication(
        cls,
        session: Session,
        *,
        exchange: Exchange,
        listing: Listing,
        trading_date: date,
    ) -> None:
        load = cls._create_load(session, exchange=exchange, trading_date=trading_date, eligible_count=1)
        classification = classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True))
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=load.id,
            listing_id=listing.id,
            job_id=None,
            classification=classification,
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        session.add(
            PriceRecord(
                listing_id=listing.id,
                trading_date=trading_date,
                price_type="current_day_unadjusted_open",
                value=Decimal("222.22"),
                currency="USD",
            )
        )
        evaluate_and_persist_opening_correctness_validation(
            session,
            exchange_day_load_id=load.id,
            benchmark_compared_count=0,
            benchmark_mismatch_count=0,
            validation_delayed=True,
            checked_at=datetime(2026, 5, 1, 14, 5, tzinfo=UTC),
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @classmethod
    def _seed_timeliness_validation_fixture(cls, session: Session, *, exchange: Exchange, listing: Listing) -> None:
        for idx in range(1, 6):
            session.add(
                ProviderAttempt(
                    attempt_key=f"nyse-attempt-{idx}",
                    provider_id=cls.provider.id,
                    exchange_id=exchange.id,
                    request_purpose="pricing",
                    load_type="current_day_open",
                    requested_at=datetime(2026, 5, 1, 13, 30, tzinfo=UTC) - timedelta(minutes=idx),
                    latency_ms=60_000 if idx <= 2 else 31 * 60 * 1000,
                    result_status="success",
                )
            )

        session.add(
            CandidatePriceValue(
                candidate_key="nyse-open-candidate",
                candidate_set_key="nyse-open-set",
                listing_id=listing.id,
                provider_id=cls.provider.id,
                provider_attempt_id=None,
                trading_date=TRADING_DATE,
                price_type="current_day_unadjusted_open",
                value=Decimal("123.45"),
                currency="USD",
                provider_request_id="nyse-open-1",
                provider_observed_at=datetime(2026, 5, 1, 13, 40, tzinfo=UTC),
                audit_metadata={
                    "selection_inputs": {
                        "benchmark_value": "123.45",
                        "calendar_reference": {
                            "expected_is_trading_day": True,
                            "reference_type": "weekday",
                            "reference_source": "official_exchange_calendar",
                        },
                    }
                },
            )
        )
        session.add(
            CandidatePriceValue(
                candidate_key="nyse-close-candidate",
                candidate_set_key="nyse-close-set",
                listing_id=listing.id,
                provider_id=cls.provider.id,
                provider_attempt_id=None,
                trading_date=date(2026, 4, 30),
                price_type="historical_adjusted_close",
                value=Decimal("122.00"),
                currency="USD",
                provider_request_id="nyse-close-1",
                provider_observed_at=datetime(2026, 5, 1, 13, 45, tzinfo=UTC),
                audit_metadata={},
            )
        )

    def _get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_m4_integration_gate_proves_fail_closed_publication_chain(self) -> None:
        status, body = self._get(
            "/app/exchanges/readiness?exchange=NYSE,NASDAQ,PSE,AMEX",
            headers={"X-App-Token": "app-token"},
        )
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        readiness_rows = {row["exchange"]: row for row in json.loads(body)["exchange_readiness"]}
        self.assertEqual(readiness_rows["NYSE"]["readiness_state"], "ready")
        self.assertTrue(readiness_rows["NYSE"]["publication_available"])
        self.assertEqual(readiness_rows["NASDAQ"]["readiness_state"], "not_ready")
        self.assertFalse(readiness_rows["NASDAQ"]["publication_available"])
        self.assertEqual(readiness_rows["PSE"]["readiness_state"], "market_closed")
        self.assertFalse(readiness_rows["PSE"]["publication_available"])
        self.assertEqual(readiness_rows["AMEX"]["readiness_state"], "not_ready")
        self.assertFalse(readiness_rows["AMEX"]["publication_available"])

        status, body = self._get("/app/exchanges/NYSE/prices/current", headers={"X-App-Token": "app-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        nyse_prices = json.loads(body)["exchange_current_day_prices"]
        self.assertEqual(nyse_prices["exchange"], "NYSE")
        self.assertEqual(nyse_prices["trading_date"], "2026-05-01")
        self.assertEqual(len(nyse_prices["current_day_prices"]), 1)
        self.assertEqual(nyse_prices["current_day_prices"][0]["symbol"], "NYSA")

        for path in (
            "/app/exchanges/NASDAQ/prices/current",
            "/app/exchanges/PSE/prices/current",
            "/app/exchanges/AMEX/prices/current",
        ):
            with self.subTest(path=path):
                status, body = self._get(path, headers={"X-App-Token": "app-token"})
                self.assertEqual(status, HTTPStatus.NOT_FOUND, msg=body)
                self.assertEqual(json.loads(body)["error"], "No ready current-day opening prices available.")

        status, body = self._get("/operator/loads/today-opening?day=2026-05-01", headers={"X-Private-Session": "operator-token"})
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        operator_rows = {row["exchange"]: row for row in json.loads(body)["operator_today_opening_load_table"]}
        self.assertEqual(operator_rows["NYSE"]["status"], "ready")
        self.assertEqual(operator_rows["NYSE"]["publication_status"], "ready")
        self.assertTrue(operator_rows["NYSE"]["publication_available"])
        self.assertEqual(operator_rows["NASDAQ"]["status"], "partial_problematic")
        self.assertTrue(operator_rows["NASDAQ"]["degraded"])
        self.assertFalse(operator_rows["NASDAQ"]["publication_available"])
        self.assertEqual(operator_rows["PSE"]["status"], "market_closed")
        self.assertEqual(operator_rows["PSE"]["quality_result"], "not_applicable")
        self.assertEqual(operator_rows["AMEX"]["publication_status"], "blocked")
        self.assertEqual(operator_rows["AMEX"]["quality_result"], "pending")
        self.assertFalse(operator_rows["AMEX"]["publication_available"])

    def test_m4_timeliness_miss_validation_marks_internal_degradation(self) -> None:
        engine = sa.create_engine(self._db_url)
        try:
            with Session(engine) as session:
                result = orchestrate_launch_exchange_validation_run(
                    session,
                    target_exchange_codes=["NYSE"],
                    run_key="m4-timeliness-gate",
                )
                session.commit()

                self.assertEqual(result.run.state, "succeeded")
                report = (
                    session.query(ValidationExchangeReport)
                    .join(ValidationRun, ValidationRun.id == ValidationExchangeReport.validation_run_id)
                    .filter(ValidationRun.run_key == "m4-timeliness-gate")
                    .one()
                )
                bucket = report.result_buckets["completeness_timeliness"]
                self.assertEqual(bucket["status"], "fail")
                self.assertIn("timeliness_threshold_not_met", bucket["findings"])
                self.assertEqual(bucket["evidence"]["timeliness"]["miss_count"], 3)
        finally:
            engine.dispose()


class _GateCalendarService:
    def evaluate(self, exchange: str, local_date: date) -> TradingDayDecision:
        if exchange.upper() == "PSE":
            return TradingDayDecision(
                exchange="PSE",
                local_date=local_date,
                status=TradingDayStatus.MARKET_CLOSED,
                calendar_id="XPRA",
            )
        return TradingDayDecision(
            exchange=exchange.upper(),
            local_date=local_date,
            status=TradingDayStatus.EXPECTED_TRADING_DAY,
            calendar_id="XNYS",
        )


if __name__ == "__main__":
    unittest.main()
