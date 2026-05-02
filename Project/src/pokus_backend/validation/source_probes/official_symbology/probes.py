from __future__ import annotations

import json
import re
from typing import Iterable, Mapping

from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
)
from pokus_backend.validation.source_probes.official_symbology.probe_http import HttpProbeResponse, fetch_http_response

NASDAQ_TRADER_SOURCE_CODE = "NASDAQ_TRADER"
NYSE_SOURCE_CODE = "NYSE"
PSE_PSE_EDGE_SOURCE_CODE = "PSE_PSE_EDGE"
OPENFIGI_SOURCE_CODE = "OPENFIGI"
NASDAQ_DATA_LINK_SOURCE_CODE = "NASDAQ_DATA_LINK"
OFFICIAL_SYMBOLOGY_SOURCE_CODES: tuple[str, ...] = (
    NASDAQ_TRADER_SOURCE_CODE,
    NYSE_SOURCE_CODE,
    PSE_PSE_EDGE_SOURCE_CODE,
    OPENFIGI_SOURCE_CODE,
    NASDAQ_DATA_LINK_SOURCE_CODE,
)
_OFFICIAL_SYMBOLOGY_SOURCE_SET = set(OFFICIAL_SYMBOLOGY_SOURCE_CODES)

_ALIAS_TO_SOURCE_CODE = {
    "NASDAQ": NASDAQ_TRADER_SOURCE_CODE,
    "NASDAQ_TRADER": NASDAQ_TRADER_SOURCE_CODE,
    "NASDAQTRADER": NASDAQ_TRADER_SOURCE_CODE,
    "NASDAQ TRADER": NASDAQ_TRADER_SOURCE_CODE,
    "NYSE": NYSE_SOURCE_CODE,
    "PSE": PSE_PSE_EDGE_SOURCE_CODE,
    "PSE_EDGE": PSE_PSE_EDGE_SOURCE_CODE,
    "PSE/PSE EDGE": PSE_PSE_EDGE_SOURCE_CODE,
    "PSE EDGE": PSE_PSE_EDGE_SOURCE_CODE,
    "PSE_PSE_EDGE": PSE_PSE_EDGE_SOURCE_CODE,
    "OPENFIGI": OPENFIGI_SOURCE_CODE,
    "OPEN_FIGI": OPENFIGI_SOURCE_CODE,
    "OPEN FIGI": OPENFIGI_SOURCE_CODE,
    "NASDAQ_DATA_LINK": NASDAQ_DATA_LINK_SOURCE_CODE,
    "NASDAQ DATALINK": NASDAQ_DATA_LINK_SOURCE_CODE,
    "NASDAQ_DATA": NASDAQ_DATA_LINK_SOURCE_CODE,
}


def build_official_symbology_probe_registry(
    *,
    fetcher=fetch_http_response,
) -> dict[str, LiveSourceProbeDefinition]:
    return {
        NASDAQ_TRADER_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=NASDAQ_TRADER_SOURCE_CODE,
            probe=lambda context: _probe_nasdaq_trader(context, fetcher=fetcher),
        ),
        NYSE_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=NYSE_SOURCE_CODE,
            probe=lambda context: _probe_nyse(context, fetcher=fetcher),
        ),
        PSE_PSE_EDGE_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=PSE_PSE_EDGE_SOURCE_CODE,
            probe=lambda context: _probe_pse_pse_edge(context, fetcher=fetcher),
        ),
        OPENFIGI_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=OPENFIGI_SOURCE_CODE,
            probe=lambda context: _probe_openfigi(context, fetcher=fetcher),
        ),
        NASDAQ_DATA_LINK_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=NASDAQ_DATA_LINK_SOURCE_CODE,
            probe=lambda context: _probe_nasdaq_data_link(context, fetcher=fetcher),
        ),
    }


def normalize_official_symbology_source_codes(source_codes: Iterable[str] | None) -> list[str]:
    if source_codes is None:
        return list(OFFICIAL_SYMBOLOGY_SOURCE_CODES)

    normalized: list[str] = []
    for source_code in source_codes:
        candidate = source_code.strip().upper().replace("-", " ").replace("  ", " ")
        if not candidate:
            continue
        resolved = _ALIAS_TO_SOURCE_CODE.get(candidate)
        if resolved is None and candidate in _OFFICIAL_SYMBOLOGY_SOURCE_SET:
            resolved = candidate
        if resolved is None:
            raise ValueError(
                "unsupported official/symbology source code="
                f"{candidate!r}; expected one of {list(OFFICIAL_SYMBOLOGY_SOURCE_CODES)}"
            )
        if resolved not in normalized:
            normalized.append(resolved)

    if not normalized:
        raise ValueError("source_codes must include at least one official/symbology source")
    return normalized


def _probe_nasdaq_trader(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher,
) -> LiveSourceProbeExecutionPayload:
    try:
        response = fetcher("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt")
    except Exception as exc:
        return _runtime_error_payload("NASDAQ_TRADER", exc)

    rows = _nasdaq_trader_rows(response.body_text)
    has_rows = response.status_code == 200 and len(rows) > 0
    if has_rows:
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes=(
                "public_download status=200; discovery_usefulness=high_for_us_listed_universe_refresh"
            ),
            speed_notes=(
                f"single_request_latency_ms={response.latency_ms}; parsed_rows={len(rows)}; "
                "identifier_usefulness=contains_exchange_symbols_but_not_figi"
            ),
            exchange_coverage_notes=(
                "Official consolidated US listings from Nasdaq Trader observed; "
                "PSE/PSE EDGE coverage not expected from this source."
            ),
            classification_verdict="promote",
            assigned_role="primary_discovery",
            observed_latency_ms=response.latency_ms,
        )

    return _http_unavailable_payload(
        source_code="NASDAQ_TRADER",
        response=response,
        exchange_notes="nasdaqtrader file unavailable or unparseable during probe window",
    )


def _probe_nyse(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher,
) -> LiveSourceProbeExecutionPayload:
    try:
        index_response = fetcher("https://ftp.nyse.com/NYSESymbolMapping/")
    except Exception as exc:
        return _runtime_error_payload("NYSE", exc)

    latest_filename = _extract_latest_nyse_mapping_filename(index_response.body_text)
    if latest_filename is None:
        return _http_unavailable_payload(
            source_code="NYSE",
            response=index_response,
            exchange_notes="NYSE symbol mapping directory reachable but mapping file link not found",
        )

    try:
        mapping_response = fetcher(f"https://ftp.nyse.com/NYSESymbolMapping/{latest_filename}")
    except Exception as exc:
        return _runtime_error_payload("NYSE", exc)

    line_count = len([line for line in mapping_response.body_text.splitlines() if line.strip()])
    has_data = mapping_response.status_code == 200 and line_count > 10
    if has_data:
        total_latency = index_response.latency_ms + mapping_response.latency_ms
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes=(
                f"public_ftp_index_and_mapping status_codes={index_response.status_code},{mapping_response.status_code}; "
                "discovery_usefulness=high_for_nyse_symbol_discovery"
            ),
            speed_notes=(
                f"latency_ms_total={total_latency}; index={index_response.latency_ms}; mapping={mapping_response.latency_ms}; "
                "identifier_usefulness=nyse_symbology_to_cqs_mapping_present"
            ),
            exchange_coverage_notes=(
                f"NYSE symbol mapping file {latest_filename} returned {line_count} non-empty lines; "
                "coverage signal is strong for NYSE/US symbology, none for PSE/PSE EDGE."
            ),
            classification_verdict="promote",
            assigned_role="primary_discovery",
            observed_latency_ms=total_latency,
        )

    return _http_unavailable_payload(
        source_code="NYSE",
        response=mapping_response,
        exchange_notes="NYSE mapping file returned without usable symbol rows",
    )


def _probe_pse_pse_edge(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher,
) -> LiveSourceProbeExecutionPayload:
    standard_url = "https://www.pse.cz/en/market-data/shares/standard-market"
    free_url = "https://www.pse.cz/en/market-data/shares/free-market"
    try:
        standard_response = fetcher(standard_url)
        free_response = fetcher(free_url)
    except Exception as exc:
        return _runtime_error_payload("PSE_PSE_EDGE", exc)

    standard_ok = (
        standard_response.status_code == 200
        and "Standard Market | Prague Stock Exchange" in standard_response.body_text
    )
    free_ok = (
        free_response.status_code == 200
        and "Free Market | Prague Stock Exchange" in free_response.body_text
    )
    if standard_ok or free_ok:
        total_latency = standard_response.latency_ms + free_response.latency_ms
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes=(
                "public_html_pages status_codes="
                f"{standard_response.status_code},{free_response.status_code}; "
                "discovery_usefulness=medium_manual_reference_only"
            ),
            speed_notes=(
                f"latency_ms_total={total_latency}; standard={standard_response.latency_ms}; free={free_response.latency_ms}; "
                "identifier_usefulness=low_no_machine_readable_identifier_map"
            ),
            exchange_coverage_notes=(
                "PSE Standard Market page reachable="
                f"{standard_ok}; Free Market page reachable={free_ok}. "
                "PSE EDGE label was not explicitly present in sampled pages; Free Market treated as EDGE-adjacent signal for follow-up validation."
            ),
            classification_verdict="validation_only",
            assigned_role="validation_only",
            observed_latency_ms=total_latency,
        )

    return _http_unavailable_payload(
        source_code="PSE_PSE_EDGE",
        response=standard_response,
        exchange_notes="PSE Standard/Free market pages unavailable during probe window",
    )


def _probe_openfigi(
    context: LiveSourceProbeExecutionContext,
    *,
    fetcher,
) -> LiveSourceProbeExecutionPayload:
    request_body = '[{"idType":"TICKER","idValue":"IBM","exchCode":"US"}]'
    headers = {"Content-Type": "application/json"}
    api_key = context.secrets.get("OPENFIGI_API_KEY", "").strip()
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    try:
        response = fetcher(
            "https://api.openfigi.com/v3/mapping",
            method="POST",
            headers=headers,
            body=request_body,
        )
    except Exception as exc:
        return _runtime_error_payload("OPENFIGI", exc)

    payload = _safe_json_parse(response.body_text)
    mapping_count = _openfigi_mapping_count(payload)
    if response.status_code == 200 and mapping_count > 0:
        rate_remaining = response.headers.get("ratelimit-remaining", "unknown")
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes=(
                f"public_api status=200; ratelimit_remaining={rate_remaining}; "
                "discovery_usefulness=low_identifier_only_source"
            ),
            speed_notes=(
                f"single_request_latency_ms={response.latency_ms}; mapping_count={mapping_count}; "
                "identifier_usefulness=high_figi_and_symbology_crosswalk"
            ),
            exchange_coverage_notes=(
                "OpenFIGI mapping succeeded for sample ticker; exchange detail present via exchCode, "
                "but no direct exchange-level listing discovery coverage for NYSE/NASDAQ/PSE feeds."
            ),
            classification_verdict="promote",
            assigned_role="symbology_normalization",
            observed_latency_ms=response.latency_ms,
        )

    error_label = _openfigi_error_label(payload)
    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes=(
            f"openfigi_unavailable status={response.status_code}; detail={error_label}; "
            "discovery_usefulness=none_until_access_restored"
        ),
        speed_notes=(
            f"single_request_latency_ms={response.latency_ms}; "
            "identifier_usefulness=unconfirmed_due_to_failed_sample"
        ),
        exchange_coverage_notes="OpenFIGI request failed; exchange-coverage impact unknown in this run.",
        classification_verdict="validation_only",
        assigned_role="validation_only",
        observed_latency_ms=response.latency_ms,
    )


def _probe_nasdaq_data_link(
    _: LiveSourceProbeExecutionContext,
    *,
    fetcher,
) -> LiveSourceProbeExecutionPayload:
    try:
        response = fetcher("https://data.nasdaq.com/api/v3/datatables/ZACKS/FC.json?ticker=AAPL")
    except Exception as exc:
        return _runtime_error_payload("NASDAQ_DATA_LINK", exc)

    payload = _safe_json_parse(response.body_text)
    has_key_error = _contains_api_key_required_error(payload)
    if response.status_code == 200:
        return LiveSourceProbeExecutionPayload(
            is_available=True,
            quota_rate_limit_notes=(
                "api_response status=200; discovery_usefulness=low_for_exchange_discovery_in_sampled_endpoint"
            ),
            speed_notes=(
                f"single_request_latency_ms={response.latency_ms}; "
                "identifier_usefulness=medium_dataset_metadata_context"
            ),
            exchange_coverage_notes=(
                "Nasdaq Data Link endpoint responded successfully; coverage is dataset-specific and not a direct official listing feed."
            ),
            classification_verdict="fallback_only",
            assigned_role="metadata_enrichment",
            observed_latency_ms=response.latency_ms,
        )

    if has_key_error:
        return LiveSourceProbeExecutionPayload(
            is_available=False,
            quota_rate_limit_notes=(
                "api_key_required status="
                f"{response.status_code}; discovery_usefulness=blocked_without_credentials"
            ),
            speed_notes=(
                f"single_request_latency_ms={response.latency_ms}; "
                "identifier_usefulness=requires_authenticated_access_for_validation"
            ),
            exchange_coverage_notes=(
                "Nasdaq Data Link returned key-required response; NYSE/NASDAQ/PSE coverage cannot be confirmed "
                "without credentials in this run."
            ),
            classification_verdict="validation_only",
            assigned_role="validation_only",
            observed_latency_ms=response.latency_ms,
        )

    return _http_unavailable_payload(
        source_code="NASDAQ_DATA_LINK",
        response=response,
        exchange_notes="Nasdaq Data Link endpoint returned an unexpected failure payload",
    )


def _runtime_error_payload(source_code: str, exc: Exception) -> LiveSourceProbeExecutionPayload:
    error_kind = type(exc).__name__
    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes=(
            f"probe_runtime_error source={source_code} kind={error_kind}; "
            "discovery_usefulness=unknown_due_to_runtime_error"
        ),
        speed_notes=f"probe_runtime_error source={source_code} kind={error_kind}",
        exchange_coverage_notes="probe execution failed before exchange-coverage evidence could be collected.",
        classification_verdict="reject",
        assigned_role=None,
        observed_latency_ms=None,
    )


def _http_unavailable_payload(
    *,
    source_code: str,
    response: HttpProbeResponse,
    exchange_notes: str,
) -> LiveSourceProbeExecutionPayload:
    content_type = response.headers.get("content-type", "unknown")
    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes=(
            f"http_unavailable source={source_code} status={response.status_code}; content_type={content_type}; "
            "discovery_usefulness=unknown"
        ),
        speed_notes=(
            f"single_request_latency_ms={response.latency_ms}; identifier_usefulness=not_confirmed"
        ),
        exchange_coverage_notes=exchange_notes,
        classification_verdict="reject",
        assigned_role=None,
        observed_latency_ms=response.latency_ms,
    )


def _nasdaq_trader_rows(body_text: str) -> list[list[str]]:
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    if not lines:
        return []

    header = lines[0].upper()
    if "SYMBOL|SECURITY NAME|" not in header:
        return []

    rows: list[list[str]] = []
    for line in lines[1:]:
        if line.upper().startswith("FILE CREATION TIME"):
            break
        values = line.split("|")
        if len(values) < 4:
            continue
        rows.append(values)
    return rows


def _extract_latest_nyse_mapping_filename(body_text: str) -> str | None:
    matches = re.findall(r"NYSESymbolMapping_(\d{8})\.txt", body_text)
    if not matches:
        return None
    latest_date = max(matches)
    return f"NYSESymbolMapping_{latest_date}.txt"


def _safe_json_parse(raw_text: str) -> object | None:
    trimmed = raw_text.strip()
    if not trimmed:
        return None
    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        return None


def _openfigi_mapping_count(payload: object | None) -> int:
    if not isinstance(payload, list):
        return 0
    total = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if isinstance(data, list):
            total += len(data)
    return total


def _openfigi_error_label(payload: object | None) -> str:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            if "error" in first and isinstance(first["error"], str):
                return first["error"]
            if "warning" in first and isinstance(first["warning"], str):
                return first["warning"]
    return "no_error_payload"


def _contains_api_key_required_error(payload: object | None) -> bool:
    if not isinstance(payload, dict):
        return False
    quandl_error = payload.get("quandl_error")
    if not isinstance(quandl_error, dict):
        return False
    message = str(quandl_error.get("message", "")).lower()
    code = str(quandl_error.get("code", "")).upper()
    return "api key" in message or code.startswith("QEP")
