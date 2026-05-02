from __future__ import annotations

from pokus_backend.validation.combined_source_classification import ClassifiedSource


def select_sources_for_runtime_role(matrix: list[ClassifiedSource], *, runtime_role: str) -> tuple[str, ...]:
    role = runtime_role.strip().lower()
    return tuple(
        row.source_code
        for row in matrix
        if row.runtime_role == role and row.selectable_for_loader
    )
