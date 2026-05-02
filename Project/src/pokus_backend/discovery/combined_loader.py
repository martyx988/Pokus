from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Callable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pokus_backend.discovery.contract import DiscoveryCandidate
from pokus_backend.discovery.persistence import persist_discovery_candidates
from pokus_backend.discovery.source_registry import build_default_source_registry
from pokus_backend.discovery.supported_universe import project_supported_universe_state
from pokus_backend.domain import Exchange, Instrument, InstrumentType, Listing
from pokus_backend.validation import ClassifiedSource, select_sources_for_runtime_role
from pokus_backend.validation.combined_source_classification import DEFAULT_COMBINED_CLASSIFICATION_ARTIFACT_PATH

SourceDiscoveryLoader = Callable[[Sequence[str], Sequence[str]], Sequence[DiscoveryCandidate]]


@dataclass(frozen=True, slots=True)
class CombinedUniverseLoaderResult:
    effective_day: date
    selected_sources: tuple[str, ...]
    selected_listing_ids: tuple[int, ...]
    persisted_candidate_count: int
    projected_supported_listing_count: int


def execute_combined_universe_loader(
    session: Session,
    *,
    source_registry: Mapping[str, SourceDiscoveryLoader] | None = None,
    effective_day: date | None = None,
) -> CombinedUniverseLoaderResult:
    resolved_effective_day = effective_day or datetime.now(UTC).date()
    matrix = _load_matrix()
    selected_sources = _select_runtime_sources(matrix)
    resolved_registry = source_registry or build_default_source_registry()
    exchange_codes = _launch_exchange_codes(session)
    instrument_type_codes = _launch_instrument_type_codes(session)

    candidates_by_key: dict[tuple[str, str, str], DiscoveryCandidate] = {}
    persisted_count = 0
    for source_code in selected_sources:
        loader = resolved_registry.get(source_code)
        if loader is None:
            continue
        raw_candidates = loader(exchange_codes, instrument_type_codes)
        normalized_candidates = [_normalize_candidate(row) for row in raw_candidates]
        persisted = persist_discovery_candidates(
            session,
            normalized_candidates,
            provider_code=source_code,
            effective_day=resolved_effective_day,
        )
        persisted_count += len(persisted.listing_ids)
        for candidate in normalized_candidates:
            key = (candidate.exchange, candidate.instrument_type, candidate.symbol)
            if key not in candidates_by_key:
                candidates_by_key[key] = candidate
            else:
                merged_identifiers = dict(candidates_by_key[key].stable_identifiers)
                merged_identifiers.update(candidate.stable_identifiers)
                candidates_by_key[key] = DiscoveryCandidate(
                    exchange=candidate.exchange,
                    instrument_type=candidate.instrument_type,
                    symbol=candidate.symbol,
                    name=candidates_by_key[key].name,
                    stable_identifiers=merged_identifiers,
                )

    selected_listing_ids = _resolve_listing_ids(session=session, selected_keys=tuple(candidates_by_key.keys()))
    projection = project_supported_universe_state(
        session,
        selected_listing_ids=selected_listing_ids,
        supported_exchange_codes=exchange_codes,
        supported_instrument_type_codes=instrument_type_codes,
        effective_day=resolved_effective_day,
    )
    return CombinedUniverseLoaderResult(
        effective_day=resolved_effective_day,
        selected_sources=selected_sources,
        selected_listing_ids=tuple(selected_listing_ids),
        persisted_candidate_count=persisted_count,
        projected_supported_listing_count=len(projection.supported_listing_ids),
    )


def _normalize_candidate(candidate: DiscoveryCandidate) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        exchange=candidate.exchange.strip().upper(),
        instrument_type=candidate.instrument_type.strip().upper(),
        symbol=candidate.symbol.strip().upper(),
        name=candidate.name.strip(),
        stable_identifiers={key.strip().lower(): value.strip() for key, value in candidate.stable_identifiers.items()},
    )


def _load_matrix() -> list[ClassifiedSource]:
    payload = DEFAULT_COMBINED_CLASSIFICATION_ARTIFACT_PATH.read_text(encoding="utf-8")
    rows = json.loads(payload).get("matrix", [])
    return [
        ClassifiedSource(
            source_code=str(row["source_code"]).strip().upper(),
            milestone_verdict=str(row["milestone_verdict"]).strip().lower(),
            runtime_role=str(row["runtime_role"]).strip().lower(),
            selectable_for_loader=bool(row["selectable_for_loader"]),
            evidence_origin=str(row["evidence_origin"]).strip(),
        )
        for row in rows
    ]


def _select_runtime_sources(matrix: list[ClassifiedSource]) -> tuple[str, ...]:
    ordered_sources: list[str] = []
    for runtime_role in (
        "primary_discovery",
        "fallback_discovery",
        "symbology_normalization",
        "metadata_enrichment",
    ):
        for source_code in select_sources_for_runtime_role(matrix, runtime_role=runtime_role):
            if source_code not in ordered_sources:
                ordered_sources.append(source_code)
    return tuple(ordered_sources)


def _launch_exchange_codes(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(Exchange.code).where(Exchange.is_launch_active.is_(True)).order_by(Exchange.code.asc())
        )
    )


def _launch_instrument_type_codes(session: Session) -> list[str]:
    return list(
        session.scalars(
            select(InstrumentType.code)
            .where(InstrumentType.is_launch_active.is_(True))
            .order_by(InstrumentType.code.asc())
        )
    )


def _resolve_listing_ids(
    *,
    session: Session,
    selected_keys: Sequence[tuple[str, str, str]],
) -> list[int]:
    listing_ids: list[int] = []
    for exchange_code, instrument_type_code, symbol in selected_keys:
        listing_id = session.scalar(
            select(Listing.id)
            .join(Exchange, Exchange.id == Listing.exchange_id)
            .join(Instrument, Instrument.id == Listing.instrument_id)
            .join(InstrumentType, InstrumentType.id == Instrument.instrument_type_id)
            .where(
                Exchange.code == exchange_code,
                InstrumentType.code == instrument_type_code,
                Listing.symbol == symbol,
            )
        )
        if listing_id is not None:
            listing_ids.append(listing_id)
    return listing_ids
