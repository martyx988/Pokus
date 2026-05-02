from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.validation.source_probes.official_symbology.probe_http import HttpProbeResponse
from pokus_backend.validation.source_probes.official_symbology.runner import run_official_symbology_source_probes


class M31T68OfficialSymbologyRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_runner_persists_family_records_and_writes_artifact(self) -> None:
        def _fake_fetcher(url: str, **kwargs: object) -> HttpProbeResponse:
            if "nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt" in url:
                return HttpProbeResponse(
                    status_code=200,
                    headers={"content-type": "text/plain"},
                    body_text=(
                        "Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|"
                        "Financial Status|CQS Symbol|NASDAQ Symbol|NextShares\n"
                        "AAPL|APPLE INC|Q|Q|N|100|N|N|AAPL|AAPL|N\n"
                        "IBM|INTL BUSINESS MACHINES CORP|N|N|N|100|N|N|IBM|IBM|N\n"
                        "File Creation Time: 202605021030\n"
                    ),
                    latency_ms=91,
                )
            if url.endswith("/NYSESymbolMapping/"):
                return HttpProbeResponse(
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body_text=(
                        '<a href="NYSESymbolMapping_20260502.txt">NYSESymbolMapping_20260502.txt</a>'
                    ),
                    latency_ms=77,
                )
            if "NYSESymbolMapping_20260502.txt" in url:
                return HttpProbeResponse(
                    status_code=200,
                    headers={"content-type": "text/plain"},
                    body_text=(
                        "A|A|1|N|N|100|1\n"
                        "IBM|IBM|2|N|N|100|1\n"
                        "MSFT|MSFT|3|Q|Q|100|1\n"
                        "BRK.A|BRK.A|4|N|N|1|1\n"
                        "GE|GE|5|N|N|100|1\n"
                        "KO|KO|6|N|N|100|1\n"
                        "T|T|7|N|N|100|1\n"
                        "V|V|8|N|N|100|1\n"
                        "WMT|WMT|9|N|N|100|1\n"
                        "XOM|XOM|10|N|N|100|1\n"
                        "ZTS|ZTS|11|N|N|100|1\n"
                    ),
                    latency_ms=95,
                )
            if url.endswith("/market-data/shares/standard-market"):
                return HttpProbeResponse(
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body_text="<title>Standard Market | Prague Stock Exchange</title>",
                    latency_ms=66,
                )
            if url.endswith("/market-data/shares/free-market"):
                return HttpProbeResponse(
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body_text="<title>Free Market | Prague Stock Exchange</title>",
                    latency_ms=64,
                )
            if "api.openfigi.com/v3/mapping" in url:
                self.assertEqual(kwargs.get("method"), "POST")
                return HttpProbeResponse(
                    status_code=200,
                    headers={"content-type": "application/json", "ratelimit-remaining": "24"},
                    body_text=(
                        '[{"data":[{"figi":"BBG000BLNNH6","ticker":"IBM","exchCode":"US"}]}]'
                    ),
                    latency_ms=72,
                )
            if "data.nasdaq.com/api/v3/datatables/ZACKS/FC.json" in url:
                return HttpProbeResponse(
                    status_code=403,
                    headers={"content-type": "application/json"},
                    body_text=(
                        '{"quandl_error":{"code":"QEPx04","message":"A valid API key is required to retrieve data."}}'
                    ),
                    latency_ms=58,
                )
            raise AssertionError(f"unexpected probe url: {url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_path = Path(tmp_dir) / "t68-artifact.json"
            run_result, written_artifact = run_official_symbology_source_probes(
                self.session,
                validation_run_key="m3.1-t68-test-run",
                source_codes=["NASDAQ_TRADER", "NYSE", "PSE", "OPENFIGI", "NASDAQ_DATA_LINK"],
                artifact_output_path=artifact_path,
                env={},
            )

            self.assertEqual(run_result.succeeded_count, 5)
            self.assertEqual(run_result.failed_count, 0)
            self.assertEqual(run_result.skipped_count, 0)
            self.assertEqual(written_artifact, artifact_path)
            self.assertTrue(artifact_path.exists())

            artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact_payload["task_id"], "T68")
            self.assertEqual(artifact_payload["summary"]["source_count"], 5)
            self.assertEqual(len(artifact_payload["source_validation_records"]), 5)

            by_source = {
                row["source_code"]: row
                for row in artifact_payload["source_validation_records"]
            }
            self.assertEqual(by_source["OPENFIGI"]["assigned_role"], "symbology_normalization")
            self.assertEqual(by_source["OPENFIGI"]["classification_verdict"], "promote")
            self.assertEqual(by_source["NASDAQ_DATA_LINK"]["classification_verdict"], "validation_only")
            self.assertIn("PSE EDGE", by_source["PSE_PSE_EDGE"]["exchange_coverage_notes"])


if __name__ == "__main__":
    unittest.main()