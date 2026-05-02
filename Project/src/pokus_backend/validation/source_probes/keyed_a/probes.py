from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from pokus_backend.validation.live_source_probe_runner import (
    LiveSourceProbeDefinition,
    LiveSourceProbeExecutionContext,
    LiveSourceProbeExecutionPayload,
)
from pokus_backend.validation.source_probes.keyed_a.http_json import SourceProbeHttpError, fetch_json_http

KEYED_A_SOURCE_CODES: tuple[str, ...] = ("EODHD", "FMP", "FINNHUB", "ALPHA_VANTAGE")
_KEYED_A_SOURCE_SET = set(KEYED_A_SOURCE_CODES)


@dataclass(frozen=True, slots=True)
class _CoverageSummary:
    us_hit_count: int
    pse_hit_count: int


def build_keyed_a_probe_registry() -> dict[str, LiveSourceProbeDefinition]:
    return {
        "EODHD": LiveSourceProbeDefinition(
            source_code="EODHD",
            probe=_probe_eodhd,
            secret_mode="required",
            secret_env_vars=("EODHD_API_KEY",),
        ),
        "FMP": LiveSourceProbeDefinition(
            source_code="FMP",
            probe=_probe_fmp,
            secret_mode="required",
            secret_env_vars=("FMP_API_KEY",),
        ),
        "FINNHUB": LiveSourceProbeDefinition(
            source_code="FINNHUB",
            probe=_probe_finnhub,
            secret_mode="required",
            secret_env_vars=("FINNHUB_API_KEY",),
        ),
        "ALPHA_VANTAGE": LiveSourceProbeDefinition(
            source_code="ALPHA_VANTAGE",
            probe=_probe_alpha_vantage,
            secret_mode="required",
            secret_env_vars=("ALPHA_VANTAGE_API_KEY",),
        ),
    }


def normalize_keyed_a_source_codes(source_codes: Iterable[str] | None) -> list[str]:
    if source_codes is None:
        return list(KEYED_A_SOURCE_CODES)

    normalized: list[str] = []
    for source_code in source_codes:
        candidate = source_code.strip().upper()
        if not candidate:
            continue
        if candidate not in _KEYED_A_SOURCE_SET:
            raise ValueError(
                f"unsupported keyed-a source code={candidate!r}; expected one of {list(KEYED_A_SOURCE_CODES)}"
            )
        if candidate not in normalized:
            normalized.append(candidate)

    if not normalized:
        raise ValueError("source_codes must include at least one keyed-a source")
    return normalized


def keyed_a_env_with_secret_aliases(env: Mapping[str, str]) -> dict[str, str]:
    resolved = dict(env)
    _alias_into(resolved, target_env_var="EODHD_API_KEY", aliases=("EODHD_API_TOKEN", "SOURCE_PROBE_EODHD_API_KEY"))
    _alias_into(resolved, target_env_var="FMP_API_KEY", aliases=("SOURCE_PROBE_FMP_API_KEY",))
    _alias_into(resolved, target_env_var="FINNHUB_API_KEY", aliases=("SOURCE_PROBE_FINNHUB_API_KEY",))
    _alias_into(
        resolved,
        target_env_var="ALPHA_VANTAGE_API_KEY",
        aliases=("ALPHAVANTAGE_API_KEY", "SOURCE_PROBE_ALPHA_VANTAGE_API_KEY"),
    )
    return resolved


def _alias_into(resolved: dict[str, str], *, target_env_var: str, aliases: tuple[str, ...]) -> None:
    current = resolved.get(target_env_var, "")
    if current.strip():
        return
    for alias in aliases:
        value = resolved.get(alias, "")
        if value.strip():
            resolved[target_env_var] = value
            return


def _probe_eodhd(context: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    api_key = _required_key(context.secrets, "EODHD_API_KEY")
    try:
        exchanges = fetch_json_http(
            base_url="https://eodhd.com/api/exchanges-list/",
            params={"api_token": api_key, "fmt": "json"},
        )
        us_symbols = fetch_json_http(
            base_url="https://eodhd.com/api/exchange-symbol-list/US",
            params={"api_token": api_key, "fmt": "json"},
        )
        pse_symbols = fetch_json_http(
            base_url="https://eodhd.com/api/exchange-symbol-list/PSE",
            params={"api_token": api_key, "fmt": "json"},
        )
    except SourceProbeHttpError as exc:
        return _payload_from_http_error(source_code="EODHD", error=exc)

    us_count = _list_length(us_symbols.payload)
    pse_count = _list_length(pse_symbols.payload)
    coverage = _CoverageSummary(us_hit_count=us_count, pse_hit_count=pse_count)
    verdict, role = _classification_for_coverage(coverage)
    latency_ms = exchanges.elapsed_ms + us_symbols.elapsed_ms + pse_symbols.elapsed_ms
    return LiveSourceProbeExecutionPayload(
        is_available=(us_count > 0 or pse_count > 0),
        quota_rate_limit_notes=(
            "auth=required; live_calls=3; "
            f"status_codes={exchanges.status_code},{us_symbols.status_code},{pse_symbols.status_code}"
        ),
        speed_notes=(
            "latency_ms_total="
            f"{latency_ms}; exchanges={exchanges.elapsed_ms}; us_symbols={us_symbols.elapsed_ms}; pse_symbols={pse_symbols.elapsed_ms}"
        ),
        exchange_coverage_notes=(
            f"US symbol rows observed={us_count}; PSE symbol rows observed={pse_count}; "
            + _pse_interpretation(pse_count)
        ),
        classification_verdict=verdict,
        assigned_role=role,
        observed_latency_ms=latency_ms,
    )


def _probe_fmp(context: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    api_key = _required_key(context.secrets, "FMP_API_KEY")
    try:
        us_search = fetch_json_http(
            base_url="https://financialmodelingprep.com/stable/search-symbol",
            params={"query": "AAPL", "apikey": api_key},
        )
        pse_search = fetch_json_http(
            base_url="https://financialmodelingprep.com/stable/search-symbol",
            params={"query": "CEZ", "apikey": api_key},
        )
    except SourceProbeHttpError as exc:
        return _payload_from_http_error(source_code="FMP", error=exc)

    us_count = _list_length(us_search.payload)
    pse_count = _count_pse_like_matches(_as_list(pse_search.payload))
    coverage = _CoverageSummary(us_hit_count=us_count, pse_hit_count=pse_count)
    verdict, role = _classification_for_coverage(coverage)
    latency_ms = us_search.elapsed_ms + pse_search.elapsed_ms
    return LiveSourceProbeExecutionPayload(
        is_available=us_count > 0,
        quota_rate_limit_notes=(
            "auth=required; live_calls=2; "
            f"status_codes={us_search.status_code},{pse_search.status_code}"
        ),
        speed_notes=(
            "latency_ms_total="
            f"{latency_ms}; us_search={us_search.elapsed_ms}; cez_search={pse_search.elapsed_ms}"
        ),
        exchange_coverage_notes=(
            f"US ticker matches observed={us_count}; PSE-like matches in CEZ search={pse_count}; "
            + _pse_interpretation(pse_count)
        ),
        classification_verdict=verdict,
        assigned_role=role,
        observed_latency_ms=latency_ms,
    )


def _probe_finnhub(context: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    api_key = _required_key(context.secrets, "FINNHUB_API_KEY")
    try:
        us_search = fetch_json_http(
            base_url="https://finnhub.io/api/v1/search",
            params={"q": "AAPL", "token": api_key},
        )
        pse_search = fetch_json_http(
            base_url="https://finnhub.io/api/v1/search",
            params={"q": "CEZ", "token": api_key},
        )
    except SourceProbeHttpError as exc:
        return _payload_from_http_error(source_code="FINNHUB", error=exc)

    us_result = _extract_results_list(us_search.payload)
    pse_result = _extract_results_list(pse_search.payload)
    us_count = len(us_result)
    pse_count = _count_pse_like_matches(pse_result)
    coverage = _CoverageSummary(us_hit_count=us_count, pse_hit_count=pse_count)
    verdict, role = _classification_for_coverage(coverage)
    latency_ms = us_search.elapsed_ms + pse_search.elapsed_ms
    return LiveSourceProbeExecutionPayload(
        is_available=us_count > 0,
        quota_rate_limit_notes=(
            "auth=required; live_calls=2; "
            f"status_codes={us_search.status_code},{pse_search.status_code}"
        ),
        speed_notes=(
            "latency_ms_total="
            f"{latency_ms}; us_search={us_search.elapsed_ms}; cez_search={pse_search.elapsed_ms}"
        ),
        exchange_coverage_notes=(
            f"US search results observed={us_count}; PSE-like matches in CEZ search={pse_count}; "
            + _pse_interpretation(pse_count)
        ),
        classification_verdict=verdict,
        assigned_role=role,
        observed_latency_ms=latency_ms,
    )


def _probe_alpha_vantage(context: LiveSourceProbeExecutionContext) -> LiveSourceProbeExecutionPayload:
    api_key = _required_key(context.secrets, "ALPHA_VANTAGE_API_KEY")
    try:
        us_search = fetch_json_http(
            base_url="https://www.alphavantage.co/query",
            params={"function": "SYMBOL_SEARCH", "keywords": "AAPL", "apikey": api_key},
        )
        pse_search = fetch_json_http(
            base_url="https://www.alphavantage.co/query",
            params={"function": "SYMBOL_SEARCH", "keywords": "CEZ", "apikey": api_key},
        )
    except SourceProbeHttpError as exc:
        return _payload_from_http_error(source_code="ALPHA_VANTAGE", error=exc)

    us_matches = _extract_alpha_vantage_matches(us_search.payload)
    pse_matches = _extract_alpha_vantage_matches(pse_search.payload)
    us_count = len(us_matches)
    pse_count = _count_pse_like_matches(pse_matches)
    coverage = _CoverageSummary(us_hit_count=us_count, pse_hit_count=pse_count)
    verdict, role = _classification_for_coverage(coverage)
    latency_ms = us_search.elapsed_ms + pse_search.elapsed_ms
    throttled = _alpha_vantage_throttle_note(us_search.payload) or _alpha_vantage_throttle_note(pse_search.payload)
    quota_note = (
        "auth=required; live_calls=2; "
        f"status_codes={us_search.status_code},{pse_search.status_code}"
    )
    if throttled:
        quota_note = f"{quota_note}; provider_note={throttled}"
        verdict = "validation_only"
        role = "validation_only"

    return LiveSourceProbeExecutionPayload(
        is_available=(us_count > 0 or pse_count > 0),
        quota_rate_limit_notes=quota_note,
        speed_notes=(
            "latency_ms_total="
            f"{latency_ms}; us_search={us_search.elapsed_ms}; cez_search={pse_search.elapsed_ms}"
        ),
        exchange_coverage_notes=(
            f"US symbol-search matches observed={us_count}; PSE-like matches in CEZ search={pse_count}; "
            + _pse_interpretation(pse_count)
        ),
        classification_verdict=verdict,
        assigned_role=role,
        observed_latency_ms=latency_ms,
    )


def _required_key(secrets: Mapping[str, str], env_var: str) -> str:
    value = secrets.get(env_var, "").strip()
    if not value:
        raise ValueError(f"{env_var} must be present in probe secrets")
    return value


def _classification_for_coverage(coverage: _CoverageSummary) -> tuple[str, str]:
    if coverage.us_hit_count > 0 and coverage.pse_hit_count > 0:
        return "promote", "primary_discovery"
    if coverage.us_hit_count > 0 and coverage.pse_hit_count == 0:
        return "fallback_only", "fallback_discovery"
    return "validation_only", "validation_only"


def _pse_interpretation(pse_count: int) -> str:
    if pse_count > 0:
        return "PSE finding=explicit_match_present"
    return "PSE finding=none_observed_or_uncertain"


def _list_length(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    return 0


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            normalized.append(item)
    return normalized


def _extract_results_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return _as_list(payload.get("result"))


def _extract_alpha_vantage_matches(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return _as_list(payload.get("bestMatches"))


def _alpha_vantage_throttle_note(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("Note", "Information"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _count_pse_like_matches(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        flattened = " ".join(str(value).upper() for value in row.values() if value is not None)
        if "PSE" in flattened or "PRAGUE" in flattened or "CZECH" in flattened:
            count += 1
    return count


def _payload_from_http_error(source_code: str, error: SourceProbeHttpError) -> LiveSourceProbeExecutionPayload:
    payload = error.payload
    payload_hint = ""
    if isinstance(payload, dict):
        if payload.get("message"):
            payload_hint = str(payload.get("message"))
        elif payload.get("error"):
            payload_hint = str(payload.get("error"))
        elif payload.get("Error Message"):
            payload_hint = str(payload.get("Error Message"))
        elif payload.get("Note"):
            payload_hint = str(payload.get("Note"))

    note = f"probe_http_error source={source_code} kind={error} status={error.status_code}"
    if payload_hint:
        note = f"{note}; payload_hint={payload_hint}"

    return LiveSourceProbeExecutionPayload(
        is_available=False,
        quota_rate_limit_notes=note,
        speed_notes=f"probe_http_error_latency_ms={error.elapsed_ms}",
        exchange_coverage_notes=(
            "probe_http_error; "
            "PSE finding=not_tested_due_to_error"
        ),
        classification_verdict="validation_only",
        assigned_role="validation_only",
        observed_latency_ms=error.elapsed_ms,
    )

