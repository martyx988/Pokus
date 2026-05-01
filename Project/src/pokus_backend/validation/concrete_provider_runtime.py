from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from time import perf_counter
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import Exchange, Provider
from pokus_backend.pricing.candidate_value_persistence import CandidateSetAuditEvidence, persist_candidate_price_values
from pokus_backend.pricing.contract import PriceCandidate
from pokus_backend.pricing.provider_attempt_logging import ProviderAttemptLogInput, log_provider_attempt

_PROVIDER_CODE = "STOOQ"
_PROVIDER_NAME = "Stooq"


@dataclass(frozen=True, slots=True)
class ConcreteValidationRuntimeRequest:
    exchange_code: str
    listing_id: int
    symbol: str
    currency: str = "USD"


def execute_concrete_provider_runtime(
    session: Session,
    *,
    run_key: str,
    requests: list[ConcreteValidationRuntimeRequest],
) -> int:
    if not requests:
        return 0

    _get_or_create_provider(session=session)
    success_count = 0
    for request in requests:
        normalized_exchange = request.exchange_code.strip().upper()
        exchange = session.scalar(select(Exchange).where(Exchange.code == normalized_exchange))
        if exchange is None:
            raise ValueError(f"unknown exchange code: {normalized_exchange}")

        attempt_key = f"{run_key}:{normalized_exchange}:stooq:{request.symbol.strip().lower()}"
        requested_at = datetime.now(timezone.utc)
        started_at = datetime.now(timezone.utc)
        started_perf = perf_counter()

        try:
            quote = _fetch_stooq_quote(symbol=request.symbol)
            completed_at = datetime.now(timezone.utc)
            latency_ms = max(0, int((perf_counter() - started_perf) * 1000))
            attempt = log_provider_attempt(
                session,
                ProviderAttemptLogInput(
                    attempt_key=attempt_key,
                    provider_code=_PROVIDER_CODE,
                    exchange_code=normalized_exchange,
                    request_purpose="validation_runtime",
                    load_type="validation_current_and_historical",
                    requested_at=requested_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=latency_ms,
                    result_status="success",
                    normalized_metadata={"symbol": request.symbol.strip().upper(), "source": "stooq_quote_api"},
                ),
            )

            audit = CandidateSetAuditEvidence(
                candidate_set_key=f"{run_key}:{normalized_exchange}:{request.listing_id}:{quote.trading_day.isoformat()}",
                requested_at=requested_at,
                provider_attempt_key=attempt.attempt_key,
                selection_inputs={"runtime_provider": "stooq", "symbol": request.symbol.strip().upper()},
            )
            persist_candidate_price_values(
                session,
                candidates=[
                    PriceCandidate(
                        instrument_id=str(request.listing_id),
                        listing_id=str(request.listing_id),
                        exchange=normalized_exchange,
                        trading_day=quote.trading_day,
                        price_type="current_day_unadjusted_open",
                        value=quote.open_value,
                        currency=request.currency.strip().upper(),
                        provider_code=_PROVIDER_CODE,
                        provider_observed_at=quote.observed_at,
                        provider_request_id=quote.provider_request_id,
                        provider_metadata={"symbol": request.symbol.strip().upper(), "price_field": "open"},
                    ),
                    PriceCandidate(
                        instrument_id=str(request.listing_id),
                        listing_id=str(request.listing_id),
                        exchange=normalized_exchange,
                        trading_day=quote.trading_day,
                        price_type="historical_adjusted_close",
                        value=quote.close_value,
                        currency=request.currency.strip().upper(),
                        provider_code=_PROVIDER_CODE,
                        provider_observed_at=quote.observed_at,
                        provider_request_id=quote.provider_request_id,
                        provider_metadata={"symbol": request.symbol.strip().upper(), "price_field": "close"},
                    ),
                ],
                audit=audit,
            )
            success_count += 1
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            latency_ms = max(0, int((perf_counter() - started_perf) * 1000))
            log_provider_attempt(
                session,
                ProviderAttemptLogInput(
                    attempt_key=attempt_key,
                    provider_code=_PROVIDER_CODE,
                    exchange_code=normalized_exchange,
                    request_purpose="validation_runtime",
                    load_type="validation_current_and_historical",
                    requested_at=requested_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    latency_ms=latency_ms,
                    result_status="error",
                    error_code=type(exc).__name__,
                    error_detail=str(exc),
                    normalized_metadata={"symbol": request.symbol.strip().upper(), "source": "stooq_quote_api"},
                ),
            )
    session.flush()
    return success_count


@dataclass(frozen=True, slots=True)
class _StooqQuote:
    trading_day: date
    observed_at: datetime
    open_value: Decimal
    close_value: Decimal
    provider_request_id: str


def _fetch_stooq_quote(*, symbol: str) -> _StooqQuote:
    normalized_symbol = symbol.strip().lower()
    if not normalized_symbol:
        raise ValueError("symbol must be a non-empty string")

    url = f"https://stooq.com/q/l/?s={normalized_symbol}&i=d"
    try:
        payload = urlopen(url, timeout=20).read().decode("utf-8").strip()
    except URLError as exc:
        raise RuntimeError(f"stooq request failed for {normalized_symbol}: {exc}") from exc
    if not payload:
        raise RuntimeError(f"stooq returned an empty payload for {normalized_symbol}")

    parts = [segment.strip() for segment in payload.split(",")]
    if len(parts) < 8:
        raise RuntimeError(f"unexpected stooq payload format for {normalized_symbol}: {payload}")
    _, raw_day, raw_time, raw_open, _, _, raw_close, _ = parts[:8]
    if raw_day == "N/D" or raw_open == "N/D" or raw_close == "N/D":
        raise RuntimeError(f"stooq returned unavailable data for {normalized_symbol}: {payload}")

    trading_day = datetime.strptime(raw_day, "%Y%m%d").date()
    observed_at = datetime.strptime(f"{raw_day}{raw_time}", "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    return _StooqQuote(
        trading_day=trading_day,
        observed_at=observed_at,
        open_value=Decimal(raw_open),
        close_value=Decimal(raw_close),
        provider_request_id=f"stooq:{normalized_symbol}:{raw_day}:{raw_time}",
    )


def _get_or_create_provider(*, session: Session) -> Provider:
    existing = session.scalar(select(Provider).where(Provider.code == _PROVIDER_CODE))
    if existing is not None:
        return existing

    created = Provider(code=_PROVIDER_CODE, name=_PROVIDER_NAME, is_active=True, configuration={"base_url": "stooq.com"})
    session.add(created)
    session.flush()
    return created
