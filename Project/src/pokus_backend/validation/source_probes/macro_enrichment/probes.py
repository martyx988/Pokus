from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
)

MACRO_ENRICHMENT_SOURCE_CODES: tuple[str, ...] = ("FRED", "DBNOMICS", "IMF", "WORLDBANK")

_FRED_GDP_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP"
_DBNOMICS_DATASETS_URL = "https://api.db.nomics.world/v22/datasets/IMF"
_IMF_INDICATORS_URL = "https://www.imf.org/external/datamapper/api/v1/indicators"
_WORLD_BANK_GDP_URL = "https://api.worldbank.org/v2/country/US/indicator/NY.GDP.MKTP.CD?format=json&per_page=20"


@dataclass(frozen=True, slots=True)
class _HttpPayload:
    text: str
    status_code: int
    elapsed_ms: int


def build_macro_enrichment_probe_registry() -> dict[str, LiveSourceProbeDefinition]:
    return {
        "FRED": LiveSourceProbeDefinition(source_code="FRED", probe=probe_fred),
        "DBNOMICS": LiveSourceProbeDefinition(source_code="DBNOMICS", probe=probe_dbnomics),
        "IMF": LiveSourceProbeDefinition(source_code="IMF", probe=probe_imf),
        "WORLDBANK": LiveSourceProbeDefinition(source_code="WORLDBANK", probe=probe_world_bank),
    }


def probe_fred(_: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    payload = _http_get(_FRED_GDP_CSV_URL, accept="text/csv,*/*")
    rows = list(csv.reader(io.StringIO(payload.text)))
    if len(rows) <= 1:
        raise RuntimeError("FRED probe returned no observation rows")

    data_rows = [row for row in rows[1:] if len(row) >= 2 and row[0].strip() and row[1].strip()]
    if not data_rows:
        raise RuntimeError("FRED probe returned no usable GDP observations")
    latest_date, latest_value = data_rows[-1][0].strip(), data_rows[-1][1].strip()

    return LiveSourceProbeExecutionPayload(
        is_available=True,
        quota_rate_limit_notes="Live CSV endpoint responded without API-key exchange in this probe run.",
        speed_notes=f"HTTP {payload.status_code}; {len(data_rows)} GDP rows parsed.",
        exchange_coverage_notes=(
            f"Macro GDP series only (latest {latest_date}={latest_value}); "
            "not instrument listings for NYSE/NASDAQ/PSE universe discovery."
        ),
        classification_verdict="not_for_universe_loader",
        assigned_role="not_for_universe_loader",
        observed_latency_ms=payload.elapsed_ms,
    )


def probe_dbnomics(_: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    payload = _http_get(_DBNOMICS_DATASETS_URL, accept="application/json,*/*")
    parsed = json.loads(payload.text)
    docs = parsed.get("datasets", {}).get("docs", [])
    if not isinstance(docs, list) or not docs:
        raise RuntimeError("DBnomics probe returned no dataset documents")

    sample_codes = [str(item.get("code", "")).strip() for item in docs[:5]]
    sample_codes = [code for code in sample_codes if code]

    return LiveSourceProbeExecutionPayload(
        is_available=True,
        quota_rate_limit_notes="No key required for datasets listing endpoint in this probe run.",
        speed_notes=f"HTTP {payload.status_code}; {len(docs)} dataset docs parsed on first page.",
        exchange_coverage_notes=(
            "Provider-level macro datasets (sample IMF codes: "
            + ",".join(sample_codes)
            + "); no exchange-specific instrument-universe listing feed."
        ),
        classification_verdict="not_for_universe_loader",
        assigned_role="not_for_universe_loader",
        observed_latency_ms=payload.elapsed_ms,
    )


def probe_imf(_: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    payload = _http_get(_IMF_INDICATORS_URL, accept="application/json,*/*")
    parsed = json.loads(payload.text)
    indicators = parsed.get("indicators", {})
    if not isinstance(indicators, dict) or not indicators:
        raise RuntimeError("IMF probe returned no indicators")

    has_growth_indicator = "NGDP_RPCH" in indicators
    indicator_count = len(indicators)

    return LiveSourceProbeExecutionPayload(
        is_available=True,
        quota_rate_limit_notes="No API key required for DataMapper indicators endpoint in this probe run.",
        speed_notes=f"HTTP {payload.status_code}; {indicator_count} indicators listed.",
        exchange_coverage_notes=(
            f"Indicator catalog endpoint (contains NGDP_RPCH={has_growth_indicator}); "
            "macro coverage only, not symbol-level exchange universe inputs."
        ),
        classification_verdict="not_for_universe_loader",
        assigned_role="not_for_universe_loader",
        observed_latency_ms=payload.elapsed_ms,
    )


def probe_world_bank(_: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    payload = _http_get(_WORLD_BANK_GDP_URL, accept="application/json,*/*")
    parsed = json.loads(payload.text)
    if not isinstance(parsed, list) or len(parsed) < 2:
        raise RuntimeError("World Bank probe returned unexpected payload shape")

    series_rows = parsed[1]
    if not isinstance(series_rows, list) or not series_rows:
        raise RuntimeError("World Bank probe returned no data rows")

    latest_non_null = next((row for row in series_rows if row.get("value") is not None), None)
    if latest_non_null is None:
        raise RuntimeError("World Bank probe returned only null GDP values in sample window")
    latest_year = str(latest_non_null.get("date", "unknown"))
    latest_value = str(latest_non_null.get("value"))

    return LiveSourceProbeExecutionPayload(
        is_available=True,
        quota_rate_limit_notes="Public indicator endpoint responded without auth in this probe run.",
        speed_notes=f"HTTP {payload.status_code}; {len(series_rows)} annual GDP rows sampled.",
        exchange_coverage_notes=(
            f"Macro country-level GDP series (latest non-null {latest_year}={latest_value}); "
            "not an equity listing source for launch exchange universe loading."
        ),
        classification_verdict="not_for_universe_loader",
        assigned_role="not_for_universe_loader",
        observed_latency_ms=payload.elapsed_ms,
    )


def _http_get(url: str, *, accept: str) -> _HttpPayload:
    request = Request(
        url,
        headers={
            "User-Agent": "pokus-backend-source-probe/1.0",
            "Accept": accept,
        },
    )
    started = perf_counter()
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read()
            elapsed_ms = max(0, int((perf_counter() - started) * 1000))
            encoding = response.headers.get_content_charset() or "utf-8"
            return _HttpPayload(
                text=body.decode(encoding, errors="replace"),
                status_code=response.status,
                elapsed_ms=elapsed_ms,
            )
    except HTTPError as exc:
        raise RuntimeError(f"request failed for {url} with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"request failed for {url}: {exc.reason}") from exc
