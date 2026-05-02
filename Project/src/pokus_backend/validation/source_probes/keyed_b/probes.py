from __future__ import annotations

import os
from typing import Any, Mapping
from urllib.parse import urlencode

from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
)

from .probe_http import HttpJsonResponse, fetch_json_response

TIINGO_SOURCE_CODE = "TIINGO"
MARKETSTACK_SOURCE_CODE = "MARKETSTACK"
POLYGON_SOURCE_CODE = "POLYGON"
TWELVE_DATA_SOURCE_CODE = "TWELVE_DATA"
KEYED_B_SOURCE_CODES: tuple[str, ...] = (
    TIINGO_SOURCE_CODE,
    MARKETSTACK_SOURCE_CODE,
    POLYGON_SOURCE_CODE,
    TWELVE_DATA_SOURCE_CODE,
)


def build_keyed_b_probe_registry() -> dict[str, LiveSourceProbeDefinition]:
    return {
        TIINGO_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=TIINGO_SOURCE_CODE,
            probe=probe_tiingo_source,
            secret_mode="required",
            secret_env_vars=("TIINGO_API_KEY",),
        ),
        MARKETSTACK_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=MARKETSTACK_SOURCE_CODE,
            probe=probe_marketstack_source,
            secret_mode="required",
            secret_env_vars=("MARKETSTACK_API_KEY",),
        ),
        POLYGON_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=POLYGON_SOURCE_CODE,
            probe=probe_polygon_source,
            secret_mode="required",
            secret_env_vars=("POLYGON_API_KEY",),
        ),
        TWELVE_DATA_SOURCE_CODE: LiveSourceProbeDefinition(
            source_code=TWELVE_DATA_SOURCE_CODE,
            probe=probe_twelve_data_source,
            secret_mode="required",
            secret_env_vars=("TWELVE_DATA_API_KEY",),
        ),
    }


def keyed_b_env_with_secret_fallbacks(env: Mapping[str, str]) -> dict[str, str]:
    resolved = dict(env)
    _alias_or_placeholder(
        resolved,
        target_env_var="TIINGO_API_KEY",
        aliases=("SOURCE_PROBE_TIINGO_API_KEY", "TIINGO_API_TOKEN"),
    )
    _alias_or_placeholder(
        resolved,
        target_env_var="MARKETSTACK_API_KEY",
        aliases=("SOURCE_PROBE_MARKETSTACK_API_KEY",),
    )
    _alias_or_placeholder(
        resolved,
        target_env_var="POLYGON_API_KEY",
        aliases=("SOURCE_PROBE_POLYGON_API_KEY",),
    )
    _alias_or_placeholder(
        resolved,
        target_env_var="TWELVE_DATA_API_KEY",
        aliases=("SOURCE_PROBE_TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY"),
    )
    return resolved


def probe_tiingo_source(
    context: LiveSourceProbeExecutionContext,
    *,
    fetcher=fetch_json_response,
) -> LiveSourceProbeExecutionPayload:
    token = _resolved_api_key(
        context.secrets,
        primary="TIINGO_API_KEY",
        aliases=("SOURCE_PROBE_TIINGO_API_KEY", "TIINGO_API_TOKEN"),
    )
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Token {token}"
    response = fetcher(
        "https://api.tiingo.com/tiingo/daily/aapl",
        headers=headers,
    )

    if response.status_code == 200 and isinstance(response.payload, dict):
        exchange = _coalesce_text(response.payload.get("exchangeCode"), response.payload.get("exchange"))
        exchange_label = exchange or "unknown"
        return _availability_payload(
            response=response,
            quota_notes=f"auth_mode={'token' if token else 'no_token'}; single_symbol=AAPL",
            exchange_notes=(
                f"AAPL metadata returned (exchange={exchange_label}); US-oriented metadata is available, "
                "but this probe found no explicit PSE listing evidence."
            ),
            verdict="fallback_only",
            role="fallback_discovery",
        )

    error_text = _extract_error_text(response.payload, fallback=response.raw_body)
    if response.status_code in {401, 403}:
        return _auth_blocked_payload(
            response=response,
            error_text=error_text,
            source_label="Tiingo",
        )
    return _hard_failure_payload(response=response, error_text=error_text)


def probe_marketstack_source(
    context: LiveSourceProbeExecutionContext,
    *,
    fetcher=fetch_json_response,
) -> LiveSourceProbeExecutionPayload:
    key = _resolved_api_key(
        context.secrets,
        primary="MARKETSTACK_API_KEY",
        aliases=("SOURCE_PROBE_MARKETSTACK_API_KEY",),
    )
    query = {"limit": "1", "search": "AAPL"}
    if key:
        query["access_key"] = key
    url = f"https://api.marketstack.com/v1/tickers?{urlencode(query)}"
    response = fetcher(url)

    if response.status_code == 200 and isinstance(response.payload, dict):
        exchange_label = _extract_marketstack_exchange_label(response.payload)
        return _availability_payload(
            response=response,
            quota_notes=f"auth_mode={'access_key' if key else 'no_key'}; endpoint=tickers; limit=1",
            exchange_notes=(
                f"Ticker metadata response received (sample_exchange={exchange_label}); "
                "broad fallback discovery seems possible, but PSE depth is weak/unverified in this sample."
            ),
            verdict="validation_only",
            role="validation_only",
        )

    error_text = _extract_error_text(response.payload, fallback=response.raw_body)
    if response.status_code in {401, 403}:
        return _auth_blocked_payload(
            response=response,
            error_text=error_text,
            source_label="Marketstack",
        )
    return _hard_failure_payload(response=response, error_text=error_text)


def probe_polygon_source(
    context: LiveSourceProbeExecutionContext,
    *,
    fetcher=fetch_json_response,
) -> LiveSourceProbeExecutionPayload:
    key = _resolved_api_key(
        context.secrets,
        primary="POLYGON_API_KEY",
        aliases=("SOURCE_PROBE_POLYGON_API_KEY",),
    )
    query = {"ticker": "AAPL", "limit": "1", "market": "stocks"}
    if key:
        query["apiKey"] = key
    url = f"https://api.polygon.io/v3/reference/tickers?{urlencode(query)}"
    response = fetcher(url)

    if response.status_code == 200 and isinstance(response.payload, dict):
        count = response.payload.get("count")
        count_label = str(count) if count is not None else "unknown"
        return _availability_payload(
            response=response,
            quota_notes=f"auth_mode={'apiKey' if key else 'no_key'}; endpoint=reference_tickers; count={count_label}",
            exchange_notes=(
                "US ticker reference endpoint responded with usable metadata; "
                "good US discovery fallback signal, but explicit PSE evidence was not observed."
            ),
            verdict="fallback_only",
            role="fallback_discovery",
        )

    error_text = _extract_error_text(response.payload, fallback=response.raw_body)
    if response.status_code in {401, 403}:
        return _auth_blocked_payload(
            response=response,
            error_text=error_text,
            source_label="Polygon",
        )
    return _hard_failure_payload(response=response, error_text=error_text)


def probe_twelve_data_source(
    context: LiveSourceProbeExecutionContext,
    *,
    fetcher=fetch_json_response,
) -> LiveSourceProbeExecutionPayload:
    key = _resolved_api_key(
        context.secrets,
        primary="TWELVE_DATA_API_KEY",
        aliases=("SOURCE_PROBE_TWELVE_DATA_API_KEY", "TWELVEDATA_API_KEY"),
    )
    query = {"outputsize": "1"}
    if key:
        query["apikey"] = key
    url = f"https://api.twelvedata.com/stocks?{urlencode(query)}"
    response = fetcher(url)

    if response.status_code == 200 and isinstance(response.payload, dict) and response.payload.get("status") == "ok":
        return _availability_payload(
            response=response,
            quota_notes=f"auth_mode={'apikey' if key else 'no_key'}; endpoint=stocks; outputsize=1",
            exchange_notes=(
                "Reference stock catalog returned; multi-exchange metadata appears usable, "
                "but this probe did not surface explicit PSE-strength evidence."
            ),
            verdict="validation_only",
            role="validation_only",
        )

    error_text = _extract_error_text(response.payload, fallback=response.raw_body)
    auth_like_code = None
    if isinstance(response.payload, dict):
        auth_like_code = response.payload.get("code")
    if response.status_code in {401, 403} or auth_like_code == 401:
        return _auth_blocked_payload(
            response=response,
            error_text=error_text,
            source_label="TwelveData",
        )
    return _hard_failure_payload(response=response, error_text=error_text)


def _availability_payload(
    *,
    response: HttpJsonResponse,
    quota_notes: str,
    exchange_notes: str,
    verdict: str,
    role: str,
) -> LiveSourceProbeExecutionPayload:
    return LiveSourceProbeExecutionPayload(
        is_available=True,
        quota_rate_limit_notes=quota_notes,
        speed_notes=f"single_request_latency_ms={response.latency_ms}",
        exchange_coverage_notes=exchange_notes,
        classification_verdict=verdict,
        assigned_role=role,
        observed_latency_ms=response.latency_ms,
    )


def _auth_blocked_payload(
    *,
    response: HttpJsonResponse,
    error_text: str,
    source_label: str,
) -> LiveSourceProbeExecutionPayload:
    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes=f"auth_required status={response.status_code} detail={error_text}",
        speed_notes=f"single_request_latency_ms={response.latency_ms}",
        exchange_coverage_notes=(
            f"{source_label} blocked before successful metadata retrieval; "
            "US/PSE coverage could not be confirmed under current credentials."
        ),
        classification_verdict="validation_only",
        assigned_role="validation_only",
        observed_latency_ms=response.latency_ms,
    )


def _hard_failure_payload(
    *,
    response: HttpJsonResponse,
    error_text: str,
) -> LiveSourceProbeExecutionPayload:
    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes=f"probe_failed status={response.status_code} detail={error_text}",
        speed_notes=f"single_request_latency_ms={response.latency_ms}",
        exchange_coverage_notes="live probe failed before exchange-coverage evidence could be captured.",
        classification_verdict="reject",
        assigned_role=None,
        observed_latency_ms=response.latency_ms,
    )


def _extract_marketstack_exchange_label(payload: Mapping[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        exchange = data[0].get("stock_exchange")
        if isinstance(exchange, dict):
            mic = exchange.get("mic")
            if isinstance(mic, str) and mic.strip():
                return mic.strip().upper()
            acronym = exchange.get("acronym")
            if isinstance(acronym, str) and acronym.strip():
                return acronym.strip().upper()
    return "unknown"


def _first_secret_value(secrets: Mapping[str, str]) -> str | None:
    for value in secrets.values():
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _resolved_api_key(
    secrets: Mapping[str, str],
    *,
    primary: str,
    aliases: tuple[str, ...],
) -> str | None:
    if primary in secrets and secrets[primary].strip():
        return secrets[primary].strip()
    candidate = _first_secret_value(secrets)
    if candidate:
        return candidate

    primary_env = os.getenv(primary, "").strip()
    if primary_env:
        return primary_env
    for alias in aliases:
        alias_env = os.getenv(alias, "").strip()
        if alias_env:
            return alias_env
    return None


def _alias_or_placeholder(
    resolved: dict[str, str],
    *,
    target_env_var: str,
    aliases: tuple[str, ...],
) -> None:
    current = resolved.get(target_env_var, "").strip()
    if current:
        return
    for alias in aliases:
        alias_value = resolved.get(alias, "").strip()
        if alias_value:
            resolved[target_env_var] = alias_value
            return
    resolved[target_env_var] = "MISSING_KEY_LIVE_AUTH_CHECK"


def _extract_error_text(payload: Any | None, *, fallback: str) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

        status = payload.get("status")
        if isinstance(status, str) and status.strip() and status.lower() != "ok":
            error = payload.get("error")
            if isinstance(error, str) and error.strip():
                return f"{status}:{error.strip()}"
            return status.strip()

        error = payload.get("error")
        if isinstance(error, dict):
            inner_message = error.get("message")
            if isinstance(inner_message, str) and inner_message.strip():
                return inner_message.strip()
            inner_code = error.get("code")
            if isinstance(inner_code, str) and inner_code.strip():
                return inner_code.strip()
        elif isinstance(error, str) and error.strip():
            return error.strip()

    fallback_text = fallback.strip().replace("\n", " ")
    if not fallback_text:
        return "no_error_detail"
    return fallback_text[:200]


def _coalesce_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None
