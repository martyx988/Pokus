from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeRunResult, run_live_source_probes
from pokus_backend.validation.source_probes.macro_enrichment.probes import (
    MACRO_ENRICHMENT_SOURCE_CODES,
    build_macro_enrichment_probe_registry,
)


def run_macro_enrichment_source_probes(
    session: Session,
    *,
    validation_run_key: str | None = None,
    env: Mapping[str, str] | None = None,
) -> LiveSourceProbeRunResult:
    return run_live_source_probes(
        session,
        source_codes=list(MACRO_ENRICHMENT_SOURCE_CODES),
        validation_run_key=validation_run_key,
        probe_registry=build_macro_enrichment_probe_registry(),
        env=env,
    )
