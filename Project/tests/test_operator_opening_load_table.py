from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import UTC, date, datetime
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sqlalchemy as sa
from sqlalchemy.orm import Session

from pokus_backend import api
from pokus_backend.domain import Base, Exchange, Instrument, InstrumentType, Listing
from pokus_backend.domain.load_tracking_models import ExchangeDayLoad
from pokus_backend.domain.publication_models import PublicationRecord, QualityCheck
from pokus_backend.discovery.operator_opening_load_table import fetch_operator_today_opening_load_table
from pokus_backend.jobs.opening_load_outcomes import (
    OpeningLoadOutcomeInput,
    classify_opening_load_outcome,
    decide_and_persist_opening_publication_status,
    evaluate_and_persist_opening_correctness_validation,
    upsert_opening_load_outcome,
)
from pokus_backend.settings import Settings


class OperatorTodayOpeningLoadTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = tempfile.TemporaryDirectory()
        cls._db_path = Path(cls._tmp_dir.name) / "operator-table.sqlite3"
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
                ExchangeDayLoad.__table__,
                Base.metadata.tables["instrument_load_outcome"],
                PublicationRecord.__table__,
                QualityCheck.__table__,
            ],
        )

        trading_date = date(2026, 5, 1)
        with Session(engine) as session:
            stock = InstrumentType(code="STOCK", name="Stock", is_launch_active=True)
            exchanges = {
                "NYSE": Exchange(code="NYSE", name="NYSE", is_launch_active=True),
                "NASDAQ": Exchange(code="NASDAQ", name="NASDAQ", is_launch_active=True),
                "AMEX": Exchange(code="AMEX", name="AMEX", is_launch_active=True),
                "PSE": Exchange(code="PSE", name="PSE", is_launch_active=True),
                "TSX": Exchange(code="TSX", name="TSX", is_launch_active=True),
            }
            session.add(stock)
            session.add_all(exchanges.values())
            session.flush()

            cls._seed_ready_row(session, exchanges["NYSE"], stock, trading_date)
            cls._seed_blocked_row(session, exchanges["NASDAQ"], stock, trading_date)
            cls._seed_failed_row(session, exchanges["AMEX"], stock, trading_date)
            cls._seed_market_closed_row(session, exchanges["PSE"], trading_date)
            cls._seed_degraded_row(session, exchanges["TSX"], stock, trading_date)
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
            sa.Table("load_jobs", metadata, sa.Column("id", sa.BigInteger(), primary_key=True))

    @staticmethod
    def _seed_ready_row(session: Session, exchange: Exchange, stock: InstrumentType, trading_date: date) -> None:
        load = _create_load(session, exchange=exchange, trading_date=trading_date, status="ready", eligible_count=1)
        listing = _create_listing(session, exchange=exchange, stock=stock, symbol="NYSR")
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=load.id,
            listing_id=listing.id,
            job_id=None,
            classification=classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True)),
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        evaluate_and_persist_opening_correctness_validation(
            session,
            exchange_day_load_id=load.id,
            benchmark_compared_count=20,
            benchmark_mismatch_count=0,
            checked_at=datetime(2026, 5, 1, 14, 5, tzinfo=UTC),
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @staticmethod
    def _seed_blocked_row(session: Session, exchange: Exchange, stock: InstrumentType, trading_date: date) -> None:
        load = _create_load(session, exchange=exchange, trading_date=trading_date, status="ready", eligible_count=1)
        listing = _create_listing(session, exchange=exchange, stock=stock, symbol="NASB")
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=load.id,
            listing_id=listing.id,
            job_id=None,
            classification=classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True)),
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        evaluate_and_persist_opening_correctness_validation(
            session,
            exchange_day_load_id=load.id,
            benchmark_compared_count=0,
            benchmark_mismatch_count=0,
            checked_at=datetime(2026, 5, 1, 14, 5, tzinfo=UTC),
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @staticmethod
    def _seed_failed_row(session: Session, exchange: Exchange, stock: InstrumentType, trading_date: date) -> None:
        load = _create_load(session, exchange=exchange, trading_date=trading_date, status="in_progress", eligible_count=1)
        listing = _create_listing(session, exchange=exchange, stock=stock, symbol="AMXF")
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=load.id,
            listing_id=listing.id,
            job_id=None,
            classification=classify_opening_load_outcome(
                OpeningLoadOutcomeInput(has_selected_price=False, provider_failed=True)
            ),
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @staticmethod
    def _seed_market_closed_row(session: Session, exchange: Exchange, trading_date: date) -> None:
        load = _create_load(
            session,
            exchange=exchange,
            trading_date=trading_date,
            status="market_closed",
            eligible_count=0,
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    @staticmethod
    def _seed_degraded_row(session: Session, exchange: Exchange, stock: InstrumentType, trading_date: date) -> None:
        load = _create_load(
            session,
            exchange=exchange,
            trading_date=trading_date,
            status="partial_problematic",
            eligible_count=2,
        )
        listing_one = _create_listing(session, exchange=exchange, stock=stock, symbol="TSX1")
        listing_two = _create_listing(session, exchange=exchange, stock=stock, symbol="TSX2")
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=load.id,
            listing_id=listing_one.id,
            job_id=None,
            classification=classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=True)),
            occurred_at=datetime(2026, 5, 1, 14, 0, tzinfo=UTC),
        )
        upsert_opening_load_outcome(
            session,
            exchange_day_load_id=load.id,
            listing_id=listing_two.id,
            job_id=None,
            classification=classify_opening_load_outcome(OpeningLoadOutcomeInput(has_selected_price=False, stale=True)),
            occurred_at=datetime(2026, 5, 1, 14, 4, tzinfo=UTC),
        )
        decide_and_persist_opening_publication_status(
            session,
            exchange_day_load_id=load.id,
            decided_at=datetime(2026, 5, 1, 14, 6, tzinfo=UTC),
        )

    def _get(self, path: str, headers: dict[str, str] | None = None) -> tuple[int, str]:
        request = Request(f"http://127.0.0.1:{self.port}{path}", headers=headers or {}, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def test_query_layer_exposes_required_columns_and_visibility_states(self) -> None:
        rows = fetch_operator_today_opening_load_table(self._db_url, trading_date=date(2026, 5, 1))
        self.assertEqual([row.exchange for row in rows], ["AMEX", "NASDAQ", "NYSE", "PSE", "TSX"])

        row_by_exchange = {row.exchange: row for row in rows}
        expected_keys = {
            "exchange",
            "trading_date",
            "status",
            "publication_status",
            "publication_available",
            "start_time",
            "finish_time",
            "eligible_count",
            "success_count",
            "failure_count",
            "coverage_percent",
            "quality_result",
            "degraded",
            "exception_count",
        }

        for row in rows:
            self.assertTrue(expected_keys.issubset(row.__class__.__dataclass_fields__.keys()))

        self.assertEqual(row_by_exchange["NYSE"].status, "ready")
        self.assertTrue(row_by_exchange["NYSE"].publication_available)
        self.assertEqual(row_by_exchange["NYSE"].quality_result, "passed")
        self.assertFalse(row_by_exchange["NYSE"].degraded)
        self.assertEqual(row_by_exchange["NYSE"].exception_count, 0)

        self.assertEqual(row_by_exchange["NASDAQ"].status, "ready")
        self.assertEqual(row_by_exchange["NASDAQ"].publication_status, "blocked")
        self.assertFalse(row_by_exchange["NASDAQ"].publication_available)
        self.assertEqual(row_by_exchange["NASDAQ"].quality_result, "pending")
        self.assertEqual(row_by_exchange["NASDAQ"].exception_count, 1)

        self.assertEqual(row_by_exchange["AMEX"].status, "failed")
        self.assertEqual(row_by_exchange["AMEX"].publication_status, "failed")
        self.assertFalse(row_by_exchange["AMEX"].publication_available)
        self.assertEqual(row_by_exchange["AMEX"].quality_result, "failed")
        self.assertEqual(row_by_exchange["AMEX"].exception_count, 1)

        self.assertEqual(row_by_exchange["PSE"].status, "market_closed")
        self.assertEqual(row_by_exchange["PSE"].quality_result, "not_applicable")
        self.assertFalse(row_by_exchange["PSE"].publication_available)
        self.assertEqual(row_by_exchange["PSE"].coverage_percent, 0.0)

        self.assertEqual(row_by_exchange["TSX"].status, "partial_problematic")
        self.assertTrue(row_by_exchange["TSX"].degraded)
        self.assertEqual(row_by_exchange["TSX"].publication_status, "blocked")
        self.assertEqual(row_by_exchange["TSX"].exception_count, 1)

    def test_operator_endpoint_is_private_and_serializes_today_opening_rows(self) -> None:
        status, _ = self._get("/operator/loads/today-opening?day=2026-05-01")
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

        status, body = self._get(
            "/operator/loads/today-opening?day=2026-05-01",
            headers={"X-Private-Session": "operator-token"},
        )
        self.assertEqual(status, HTTPStatus.OK, msg=body)
        payload = json.loads(body)
        rows = payload["operator_today_opening_load_table"]
        self.assertEqual([row["exchange"] for row in rows], ["AMEX", "NASDAQ", "NYSE", "PSE", "TSX"])
        blocked_row = next(row for row in rows if row["exchange"] == "NASDAQ")
        self.assertEqual(blocked_row["status"], "ready")
        self.assertEqual(blocked_row["publication_status"], "blocked")
        self.assertFalse(blocked_row["publication_available"])
        self.assertEqual(blocked_row["quality_result"], "pending")
        self.assertEqual(blocked_row["exception_count"], 1)
        self.assertIsInstance(blocked_row["start_time"], str)
        self.assertIsInstance(blocked_row["finish_time"], str)


def _create_load(
    session: Session,
    *,
    exchange: Exchange,
    trading_date: date,
    status: str,
    eligible_count: int,
) -> ExchangeDayLoad:
    load = ExchangeDayLoad(
        exchange_id=exchange.id,
        trading_date=trading_date,
        load_type="daily_open",
        status=status,
        eligible_instrument_count=eligible_count,
        succeeded_count=0,
        failed_count=0,
    )
    session.add(load)
    session.flush()
    return load


def _create_listing(
    session: Session,
    *,
    exchange: Exchange,
    stock: InstrumentType,
    symbol: str,
) -> Listing:
    instrument = Instrument(instrument_type_id=stock.id, canonical_name=f"{symbol} Corp")
    session.add(instrument)
    session.flush()
    listing = Listing(instrument_id=instrument.id, exchange_id=exchange.id, symbol=symbol)
    session.add(listing)
    session.flush()
    return listing


if __name__ == "__main__":
    unittest.main()
