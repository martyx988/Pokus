from __future__ import annotations

import csv
import json
from io import StringIO
from urllib.parse import urlencode
from typing import Callable

from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
)

from .http_fetch import fetch_text

_YFINANCE_SAMPLE_SYMBOLS = ("AAPL", "MSFT", "CEZ.PR")
_YFINANCE_URL_TEMPLATE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

_STOOQ_URL = "https://stooq.com/q/l/?s=aapl.us,msft.us,cez.pr&i=d"

_AKSHARE_EQUIVALENT_BASE_URL = "https://72.push2.eastmoney.com/api/qt/clist/get"
_AKSHARE_EQUIVALENT_PARAMS = {
    "pn": "1",
    "pz": "5",
    "po": "1",
    "np": "1",
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": "2",
    "invt": "2",
    "fid": "f3",
    "fs": "m:105,m:106,m:107",
    "fields": "f12,f13,f14,f2,f3",
}


def build_non_keyed_live_source_probe_registry(
    *,
    fetcher: Callable[[str], object] | None = None,
) -> dict[str, LiveSourceProbeDefinition]:
    selected_fetcher = fetcher or fetch_text
    return {
        "YFINANCE": LiveSourceProbeDefinition(
            source_code="YFINANCE",
            probe=lambda context: _probe_yfinance(context, fetcher=selected_fetcher),
        ),
        "STOOQ": LiveSourceProbeDefinition(
            source_code="STOOQ",
            probe=lambda context: _probe_stooq(context, fetcher=selected_fetcher),
        ),
        "AKSHARE": LiveSourceProbeDefinition(
            source_code="AKSHARE",
            probe=lambda context: _probe_akshare_equivalent(context, fetcher=selected_fetcher),
        ),
    }


def _probe_yfinance(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher: Callable[[str], object],
) -> LiveSourceProbeExecutionPayload:
    try:
        availability_map: dict[str, bool] = {}
        latencies: list[int] = []
        for symbol in _YFINANCE_SAMPLE_SYMBOLS:
            response = fetcher(_YFINANCE_URL_TEMPLATE.format(symbol=symbol))
            latencies.append(response.latency_ms)
            payload = json.loads(response.body_text)
            chart = payload.get("chart", {})
            has_error = chart.get("error") is not None
            has_result = bool(chart.get("result"))
            availability_map[symbol] = (response.status_code == 200) and has_result and not has_error
    except Exception as exc:
        error_kind = type(exc).__name__
        return LiveSourceProbeExecutionPayload(
            is_available=False,
            quota_rate_limit_notes=f"yfinance_probe_error:{error_kind}",
            speed_notes=f"probe_failed_before_latency_window:{error_kind}",
            exchange_coverage_notes="probe_failed_for_sample_symbols",
            classification_verdict="validation_only",
            assigned_role="validation_only",
            observed_latency_ms=None,
        )

    resolved_latency = _resolve_latency(latencies)
    covered = [symbol for symbol, available in availability_map.items() if available]
    missing = [symbol for symbol, available in availability_map.items() if not available]
    is_available = len(covered) >= 2
    coverage_note = (
        f"sample_symbols_covered:{','.join(covered)};sample_symbols_missing:{','.join(missing)}"
        if missing
        else f"sample_symbols_covered:{','.join(covered)}"
    )
    if is_available:
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes="No authentication required; unofficial endpoint may throttle without notice.",
            speed_notes=f"median_latency_ms={resolved_latency};sample_count={len(latencies)}",
            exchange_coverage_notes=coverage_note,
            classification_verdict="fallback_only",
            assigned_role="fallback_discovery",
            observed_latency_ms=resolved_latency,
        )

    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes="Live endpoint returned incomplete sample coverage during probe window.",
        speed_notes=f"median_latency_ms={resolved_latency};sample_count={len(latencies)}",
        exchange_coverage_notes=coverage_note,
        classification_verdict="validation_only",
        assigned_role="validation_only",
        observed_latency_ms=resolved_latency,
    )


def _probe_stooq(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher: Callable[[str], object],
) -> LiveSourceProbeExecutionPayload:
    try:
        response = fetcher(_STOOQ_URL)
        body_lower = response.body_text.lower()
        if "apikey" in body_lower and "captcha" in body_lower:
            return LiveSourceProbeExecutionPayload(
                is_available=False,
                quota_rate_limit_notes="Stooq now requires manual apikey + captcha bootstrap in live probe output.",
                speed_notes=f"latency_ms={response.latency_ms};status_code={response.status_code}",
                exchange_coverage_notes="automated_csv_discovery_blocked_by_manual_api_key_bootstrap",
                classification_verdict="validation_only",
                assigned_role="validation_only",
                observed_latency_ms=response.latency_ms,
            )

        parsed_rows = list(csv.DictReader(StringIO(response.body_text)))
        has_rows = bool(parsed_rows)
        has_any_price = any(
            row.get("Close", "").strip().upper() not in {"", "N/D"}
            for row in parsed_rows
        )
        coverage_note = f"rows={len(parsed_rows)};priced_rows={int(has_any_price)}"
        if has_rows and has_any_price:
            return LiveSourceProbeExecutionPayload(
                is_available=True,
                quota_rate_limit_notes="No key observed in this response path; monitor for anti-bot changes.",
                speed_notes=f"latency_ms={response.latency_ms};status_code={response.status_code}",
                exchange_coverage_notes=coverage_note,
                classification_verdict="fallback_only",
                assigned_role="fallback_discovery",
                observed_latency_ms=response.latency_ms,
            )
    except Exception as exc:
        error_kind = type(exc).__name__
        return LiveSourceProbeExecutionPayload(
            is_available=False,
            quota_rate_limit_notes=f"stooq_probe_error:{error_kind}",
            speed_notes=f"probe_failed:{error_kind}",
            exchange_coverage_notes="probe_failed_for_stooq_csv_path",
            classification_verdict="validation_only",
            assigned_role="validation_only",
            observed_latency_ms=None,
        )

    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes="Stooq response returned no usable priced rows in live probe window.",
        speed_notes=f"latency_ms={response.latency_ms};status_code={response.status_code}",
        exchange_coverage_notes=coverage_note,
        classification_verdict="validation_only",
        assigned_role="validation_only",
        observed_latency_ms=response.latency_ms,
    )


def _probe_akshare_equivalent(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher: Callable[[str], object],
) -> LiveSourceProbeExecutionPayload:
    try:
        url = f"{_AKSHARE_EQUIVALENT_BASE_URL}?{urlencode(_AKSHARE_EQUIVALENT_PARAMS)}"
        response = fetcher(url)
        payload = json.loads(response.body_text)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        total = int(data.get("total", 0) or 0)
        diff = data.get("diff", [])
        rows = len(diff) if isinstance(diff, list) else len(diff or {})
        is_available = response.status_code == 200 and total > 0 and rows > 0
    except Exception as exc:
        error_kind = type(exc).__name__
        return LiveSourceProbeExecutionPayload(
            is_available=False,
            quota_rate_limit_notes=f"akshare_equivalent_probe_error:{error_kind}",
            speed_notes=f"probe_failed:{error_kind}",
            exchange_coverage_notes="probe_failed_for_akshare_equivalent_endpoint",
            classification_verdict="validation_only",
            assigned_role="validation_only",
            observed_latency_ms=None,
        )

    if is_available:
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes="No key required on sampled endpoint; upstream field formats can change.",
            speed_notes=f"latency_ms={response.latency_ms};status_code={response.status_code}",
            exchange_coverage_notes=f"returned_rows={rows};reported_total={total};focus=us_universe_sample",
            classification_verdict="fallback_only",
            assigned_role="metadata_enrichment",
            observed_latency_ms=response.latency_ms,
        )

    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes="AkShare-equivalent endpoint returned no rows during probe window.",
        speed_notes=f"latency_ms={response.latency_ms};status_code={response.status_code}",
        exchange_coverage_notes=f"returned_rows={rows};reported_total={total}",
        classification_verdict="validation_only",
        assigned_role="validation_only",
        observed_latency_ms=response.latency_ms,
    )


def _resolve_latency(latencies: list[int]) -> int:
    if not latencies:
        return 0
    ordered = sorted(latencies)
    return ordered[len(ordered) // 2]
