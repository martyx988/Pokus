from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from pokus_backend.domain.source_validation_models import SourceValidationRole, SourceValidationVerdict


DEFAULT_COMBINED_CLASSIFICATION_ARTIFACT_PATH = Path(__file__).resolve().parent / "artifacts" / "m3_1_t70_combined_source_matrix.json"


@dataclass(frozen=True, slots=True)
class SourceEvidenceRecord:
    source_code: str
    classification_verdict: str
    assigned_role: str | None
    is_available: bool
    evidence_origin: str


@dataclass(frozen=True, slots=True)
class ClassifiedSource:
    source_code: str
    milestone_verdict: str
    runtime_role: str
    selectable_for_loader: bool
    evidence_origin: str


def derive_combined_source_matrix(records: Iterable[SourceEvidenceRecord]) -> list[ClassifiedSource]:
    by_source: dict[str, SourceEvidenceRecord] = {}
    for record in records:
        by_source[record.source_code.upper()] = SourceEvidenceRecord(
            source_code=record.source_code.upper(),
            classification_verdict=record.classification_verdict.lower(),
            assigned_role=record.assigned_role.lower() if record.assigned_role else None,
            is_available=record.is_available,
            evidence_origin=record.evidence_origin,
        )

    matrix: list[ClassifiedSource] = []
    for source_code in sorted(by_source):
        row = by_source[source_code]
        runtime_role = _runtime_role_for_record(row)
        matrix.append(
            ClassifiedSource(
                source_code=source_code,
                milestone_verdict=row.classification_verdict,
                runtime_role=runtime_role,
                selectable_for_loader=runtime_role
                in {
                    SourceValidationRole.PRIMARY_DISCOVERY.value,
                    SourceValidationRole.METADATA_ENRICHMENT.value,
                    SourceValidationRole.SYMBOLOGY_NORMALIZATION.value,
                    SourceValidationRole.FALLBACK_DISCOVERY.value,
                },
                evidence_origin=row.evidence_origin,
            )
        )
    return matrix


def build_combined_source_matrix_from_artifacts() -> list[ClassifiedSource]:
    records: list[SourceEvidenceRecord] = []
    records.extend(_records_from_non_keyed_t65())
    records.extend(_records_from_keyed_a_t66())
    records.extend(_records_from_keyed_b_t67())
    records.extend(_records_from_official_symbology_t68())
    records.extend(_records_from_macro_enrichment_t69())
    return derive_combined_source_matrix(records)


def persist_combined_matrix_artifact(
    matrix: Iterable[ClassifiedSource],
    *,
    artifact_path: Path = DEFAULT_COMBINED_CLASSIFICATION_ARTIFACT_PATH,
) -> Path:
    payload = {
        "task_id": "T70",
        "matrix": [asdict(row) for row in matrix],
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_path


def _runtime_role_for_record(record: SourceEvidenceRecord) -> str:
    verdict = record.classification_verdict
    if verdict == SourceValidationVerdict.PROMOTE.value:
        if record.assigned_role in {
            SourceValidationRole.PRIMARY_DISCOVERY.value,
            SourceValidationRole.METADATA_ENRICHMENT.value,
            SourceValidationRole.SYMBOLOGY_NORMALIZATION.value,
            SourceValidationRole.FALLBACK_DISCOVERY.value,
        }:
            return record.assigned_role
        return SourceValidationRole.FALLBACK_DISCOVERY.value
    if verdict == SourceValidationVerdict.FALLBACK_ONLY.value:
        return SourceValidationRole.FALLBACK_DISCOVERY.value
    if verdict == SourceValidationVerdict.VALIDATION_ONLY.value:
        return SourceValidationRole.VALIDATION_ONLY.value
    if verdict in {
        SourceValidationVerdict.NOT_FOR_UNIVERSE_LOADER.value,
        SourceValidationVerdict.REJECT.value,
    }:
        return SourceValidationRole.NOT_FOR_UNIVERSE_LOADER.value
    raise ValueError(f"Unsupported classification_verdict: {verdict}")


def _records_from_non_keyed_t65() -> list[SourceEvidenceRecord]:
    rows = _load_json(
        Path(__file__).resolve().parent / "source_probes" / "non_keyed" / "artifacts" / "m3_1_t65_live_probe_results.json"
    )["persisted_records"]
    return _records_from_rows(rows, "T65")


def _records_from_keyed_a_t66() -> list[SourceEvidenceRecord]:
    rows = _load_json(
        Path(__file__).resolve().parent / "source_probes" / "keyed_a" / "artifacts" / "t66_keyed_a_latest.json"
    )["source_validation_records"]
    return _records_from_rows(rows, "T66")


def _records_from_keyed_b_t67() -> list[SourceEvidenceRecord]:
    rows = _load_json(
        Path(__file__).resolve().parent / "source_probes" / "keyed_b" / "artifacts" / "t67_keyed_b_live_probe_evidence.json"
    )["records"]
    return _records_from_rows(rows, "T67")


def _records_from_official_symbology_t68() -> list[SourceEvidenceRecord]:
    rows = _load_json(
        Path(__file__).resolve().parent
        / "source_probes"
        / "official_symbology"
        / "artifacts"
        / "m3_1_t68_live_probe_results.json"
    )["source_validation_records"]
    return _records_from_rows(rows, "T68")


def _records_from_macro_enrichment_t69() -> list[SourceEvidenceRecord]:
    rows = _load_json(
        Path(__file__).resolve().parent
        / "source_probes"
        / "macro_enrichment"
        / "evidence"
        / "m31_t69_live_probe_2026-05-02.json"
    )["records"]
    return _records_from_rows(rows, "T69")


def _records_from_rows(rows: list[dict[str, Any]], evidence_origin: str) -> list[SourceEvidenceRecord]:
    return [
        SourceEvidenceRecord(
            source_code=str(row["source_code"]),
            classification_verdict=str(row["classification_verdict"]),
            assigned_role=row.get("assigned_role"),
            is_available=bool(row.get("is_available", False)),
            evidence_origin=evidence_origin,
        )
        for row in rows
    ]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
