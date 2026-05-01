from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import PriceRecord
from pokus_backend.pricing.adapter import PriceCandidateRequest, ProviderPriceAdapter
from pokus_backend.pricing.candidate_value_persistence import CandidateSetAuditEvidence, persist_candidate_price_values
from pokus_backend.pricing.source_prioritization import (
    SourcePrioritizationCandidate,
    SourceSelectionResult,
    select_source_candidate,
)


@dataclass(frozen=True, slots=True)
class OpeningLoadSourcePolicy:
    reliability_score: Decimal
    historical_availability_ratio: Decimal
    exchange_coverage_quality: Decimal
    fixed_source_order: int


@dataclass(frozen=True, slots=True)
class OpeningLoadInstrumentResult:
    selected_candidate_key: str
    selection: SourceSelectionResult
    selected_price_record_id: int


def execute_opening_load_for_instrument_day(
    session: Session,
    *,
    adapter: ProviderPriceAdapter,
    request: PriceCandidateRequest,
    audit: CandidateSetAuditEvidence,
    source_policy_by_provider: Mapping[str, OpeningLoadSourcePolicy],
) -> OpeningLoadInstrumentResult | None:
    candidates = list(adapter.fetch_current_day_open_candidates(request))
    if not candidates:
        return None

    persisted_candidates = persist_candidate_price_values(session, candidates=candidates, audit=audit)
    _validate_opening_candidates(persisted_candidates)

    normalized_policy_by_provider = {code.strip().upper(): policy for code, policy in source_policy_by_provider.items()}

    prioritization_candidates: list[SourcePrioritizationCandidate] = []
    for persisted in persisted_candidates:
        provider_code = persisted.provider.code
        if provider_code not in normalized_policy_by_provider:
            raise ValueError(f"missing source policy for provider: {provider_code}")
        policy = normalized_policy_by_provider[provider_code]
        prioritization_candidates.append(
            SourcePrioritizationCandidate(
                candidate_key=persisted.candidate_key,
                provider_code=provider_code,
                value=Decimal(str(persisted.value)),
                reliability_score=policy.reliability_score,
                historical_availability_ratio=policy.historical_availability_ratio,
                exchange_coverage_quality=policy.exchange_coverage_quality,
                fixed_source_order=policy.fixed_source_order,
            )
        )

    selection = select_source_candidate(prioritization_candidates)
    selected = next(row for row in persisted_candidates if row.candidate_key == selection.winner.candidate_key)

    existing = session.scalar(
        select(PriceRecord).where(
            PriceRecord.listing_id == selected.listing_id,
            PriceRecord.trading_date == selected.trading_date,
            PriceRecord.price_type == selected.price_type,
        )
    )
    if existing is None:
        existing = PriceRecord(
            listing_id=selected.listing_id,
            trading_date=selected.trading_date,
            price_type=selected.price_type,
            value=selected.value,
            currency=selected.currency,
            provider_attempt_id=selected.provider_attempt_id,
        )
        session.add(existing)
    else:
        existing.value = selected.value
        existing.currency = selected.currency
        existing.provider_attempt_id = selected.provider_attempt_id

    session.flush()

    return OpeningLoadInstrumentResult(
        selected_candidate_key=selected.candidate_key,
        selection=selection,
        selected_price_record_id=existing.id,
    )


def _validate_opening_candidates(candidates: list) -> None:
    first = candidates[0]
    expected_listing_id = first.listing_id
    expected_trading_date = first.trading_date
    expected_price_type = first.price_type

    if expected_price_type != "current_day_unadjusted_open":
        raise ValueError("opening-load candidates must use current_day_unadjusted_open price_type")

    for candidate in candidates[1:]:
        if candidate.listing_id != expected_listing_id:
            raise ValueError("opening-load candidates must target a single listing")
        if candidate.trading_date != expected_trading_date:
            raise ValueError("opening-load candidates must target a single trading date")
        if candidate.price_type != expected_price_type:
            raise ValueError("opening-load candidates must use one price type")
