from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.domain.instrument_models import CandidatePriceValue, Listing
from pokus_backend.domain.reference_models import Provider, ProviderAttempt
from pokus_backend.pricing.contract import PriceCandidate


@dataclass(frozen=True, slots=True)
class CandidateSetAuditEvidence:
    candidate_set_key: str
    requested_at: datetime
    provider_attempt_key: str | None = None
    selection_inputs: Mapping[str, object] | None = None


def persist_candidate_price_values(
    session: Session,
    *,
    candidates: Sequence[PriceCandidate],
    audit: CandidateSetAuditEvidence,
) -> list[CandidatePriceValue]:
    if not audit.candidate_set_key.strip():
        raise ValueError("candidate_set_key must be a non-empty string")
    if not candidates:
        return []

    stored_records: list[CandidatePriceValue] = []
    for candidate in candidates:
        provider = _get_provider_by_code(session=session, provider_code=candidate.provider_code)
        listing = _get_listing_by_external_id(session=session, external_listing_id=candidate.listing_id)
        provider_attempt = _get_provider_attempt_by_key(session=session, attempt_key=audit.provider_attempt_key)

        evidence = {
            "provider_metadata": dict(candidate.provider_metadata),
            "selection_inputs": dict(audit.selection_inputs or {}),
            "requested_at": audit.requested_at.astimezone(timezone.utc).isoformat(),
        }
        candidate_key = _build_candidate_key(
            candidate_set_key=audit.candidate_set_key,
            provider_code=provider.code,
            listing_id=candidate.listing_id,
            trading_day=candidate.trading_day.isoformat(),
            price_type=candidate.price_type,
            value=str(candidate.value),
            currency=candidate.currency,
            provider_request_id=candidate.provider_request_id,
            provider_observed_at=(
                candidate.provider_observed_at.astimezone(timezone.utc).isoformat()
                if candidate.provider_observed_at is not None
                else None
            ),
            provider_attempt_key=audit.provider_attempt_key,
            evidence=evidence,
        )
        existing = session.scalar(
            select(CandidatePriceValue).where(CandidatePriceValue.candidate_key == candidate_key)
        )
        if existing is None:
            existing = CandidatePriceValue(
                candidate_key=candidate_key,
                candidate_set_key=audit.candidate_set_key.strip(),
                listing_id=listing.id,
                provider_id=provider.id,
                provider_attempt_id=provider_attempt.id if provider_attempt is not None else None,
                trading_date=candidate.trading_day,
                price_type=candidate.price_type,
                value=Decimal(str(candidate.value)),
                currency=candidate.currency,
                provider_request_id=candidate.provider_request_id,
                provider_observed_at=candidate.provider_observed_at,
                audit_metadata=evidence,
            )
            session.add(existing)
        else:
            existing.provider_attempt_id = provider_attempt.id if provider_attempt is not None else None
            existing.audit_metadata = evidence
        stored_records.append(existing)

    session.flush()
    return stored_records


def _build_candidate_key(**parts: object) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _get_provider_by_code(*, session: Session, provider_code: str) -> Provider:
    normalized_provider_code = provider_code.strip().upper()
    if not normalized_provider_code:
        raise ValueError("provider_code must be a non-empty string")
    provider = session.scalar(select(Provider).where(Provider.code == normalized_provider_code))
    if provider is None:
        raise ValueError(f"unknown provider code: {normalized_provider_code}")
    return provider


def _get_listing_by_external_id(*, session: Session, external_listing_id: str) -> Listing:
    try:
        listing_id = int(external_listing_id)
    except ValueError as exc:
        raise ValueError(f"listing_id must map to stored listing id: {external_listing_id}") from exc
    listing = session.scalar(select(Listing).where(Listing.id == listing_id))
    if listing is None:
        raise ValueError(f"unknown listing id: {listing_id}")
    return listing


def _get_provider_attempt_by_key(*, session: Session, attempt_key: str | None) -> ProviderAttempt | None:
    if attempt_key is None:
        return None
    normalized_attempt_key = attempt_key.strip()
    if not normalized_attempt_key:
        raise ValueError("provider_attempt_key must be non-empty when provided")
    return session.scalar(select(ProviderAttempt).where(ProviderAttempt.attempt_key == normalized_attempt_key))
