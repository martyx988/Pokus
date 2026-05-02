from __future__ import annotations

from pokus_backend.validation.combined_source_classification import ClassifiedSource


def select_sources_for_runtime_role(matrix: list[ClassifiedSource], *, runtime_role: str) -> tuple[str, ...]:
    role = runtime_role.strip().lower()
    selected: list[str] = []
    for row in matrix:
        if row.runtime_role != role or not row.selectable_for_loader:
            continue
        source_code = row.source_code.strip().upper()
        if source_code and source_code not in selected:
            selected.append(source_code)
    return tuple(selected)
