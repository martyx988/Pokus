from __future__ import annotations

import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.live_source_probe_runner import run_live_source_probes
from pokus_backend.validation.source_probes.non_keyed.http_fetch import HttpFetchResult
from pokus_backend.validation.source_probes.non_keyed.probe_registry import (
    build_non_keyed_live_source_probe_registry,
)
from pokus_backend.validation.source_validation_records import list_source_validation_records_for_run


class NonKeyedSourceProbeFamilyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_registry_runs_three_non_keyed_sources_and_persists_verdicts(self) -> None:
        def _fetcher(url: str) -> HttpFetchResult:
            if "query1.finance.yahoo.com" in url:
                return HttpFetchResult(
                    url=url,
                    status_code=200,
                    body_text=json.dumps({"chart": {"result": [{"meta": {"symbol": "sample"}}], "error": None}}),
                    latency_ms=160,
                )
            if "stooq.com" in url:
                return HttpFetchResult(
                    url=url,
                    status_code=200,
                    body_text=(
                        "Get your apikey:\n1. Open https://stooq.com/q/d/?s=aapl.us&get_apikey\n"
                        "2. Enter the captcha code."
                    ),
                    latency_ms=410,
                )
            if "push2.eastmoney.com" in url:
                return HttpFetchResult(
                    url=url,
                    status_code=200,
                    body_text=json.dumps(
                        {
                            "data": {
                                "total": 13163,
                                "diff": [
                                    {"f12": "AIOS", "f13": 105, "f14": "Test", "f2": 22.0, "f3": 136.05},
                                ],
                            }
                        }
                    ),
                    latency_ms=920,
                )
            raise AssertionError(f"Unexpected URL: {url}")

        run_result = run_live_source_probes(
            self.session,
            source_codes=[" yfinance ", "STOOQ", "akshare", "AKSHARE"],
            validation_run_key="m3.1-t65-unit-registry",
            probe_registry=build_non_keyed_live_source_probe_registry(fetcher=_fetcher),
        )
        self.session.commit()

        self.assertEqual(run_result.succeeded_count, 3)
        self.assertEqual(run_result.failed_count, 0)
        self.assertEqual(run_result.skipped_count, 0)

        rows = list_source_validation_records_for_run(self.session, validation_run_key="m3.1-t65-unit-registry")
        self.assertEqual(len(rows), 3)
        by_source = {row.source_code: row for row in rows}

        self.assertTrue(by_source["YFINANCE"].is_available)
        self.assertEqual(by_source["YFINANCE"].classification_verdict, "fallback_only")
        self.assertEqual(by_source["YFINANCE"].assigned_role, "fallback_discovery")
        self.assertIn("sample_symbols_covered:AAPL,MSFT,CEZ.PR", by_source["YFINANCE"].exchange_coverage_notes)

        self.assertFalse(by_source["STOOQ"].is_available)
        self.assertEqual(by_source["STOOQ"].classification_verdict, "validation_only")
        self.assertEqual(by_source["STOOQ"].assigned_role, "validation_only")
        self.assertIn("apikey", by_source["STOOQ"].quota_rate_limit_notes.lower())

        self.assertTrue(by_source["AKSHARE"].is_available)
        self.assertEqual(by_source["AKSHARE"].classification_verdict, "fallback_only")
        self.assertEqual(by_source["AKSHARE"].assigned_role, "metadata_enrichment")

    def test_yfinance_probe_captures_fetch_errors_without_runner_failure(self) -> None:
        def _failing_fetcher(url: str) -> HttpFetchResult:
            if "query1.finance.yahoo.com" in url:
                raise RuntimeError("network unavailable")
            raise AssertionError(f"Unexpected URL: {url}")

        run_result = run_live_source_probes(
            self.session,
            source_codes=["YFINANCE"],
            validation_run_key="m3.1-t65-unit-error-capture",
            probe_registry=build_non_keyed_live_source_probe_registry(fetcher=_failing_fetcher),
        )
        self.session.commit()

        self.assertEqual(run_result.succeeded_count, 1)
        self.assertEqual(run_result.failed_count, 0)
        row = list_source_validation_records_for_run(
            self.session,
            validation_run_key="m3.1-t65-unit-error-capture",
        )[0]
        self.assertFalse(row.is_available)
        self.assertEqual(row.classification_verdict, "validation_only")
        self.assertIn("yfinance_probe_error", row.quota_rate_limit_notes)


if __name__ == "__main__":
    unittest.main()

