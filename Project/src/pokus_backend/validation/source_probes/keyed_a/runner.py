from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from sqlalchemy.orm import Session

from pokus_backend.validation.live_source_probe_runner import LiveSourceProbeRunResult, run_live_source_probes
from pokus_backend.validation.source_probes.keyed_a.artifacts import (
    collect_keyed_a_records_for_run,
    default_keyed_a_artifact_path,
    write_keyed_a_validation_artifact,
)
from pokus_backend.validation.source_probes.keyed_a.probes import (
    build_keyed_a_probe_registry,
    keyed_a_env_with_secret_aliases,
    normalize_keyed_a_source_codes,
)


def run_keyed_a_source_probes(
    session: Session,
    *,
    validation_run_key: str | None = None,
    source_codes: list[str] | None = None,
    env: Mapping[str, str] | None = None,
    artifact_output_path: Path | None = None,
) -> tuple[LiveSourceProbeRunResult, Path]:
    selected_sources = normalize_keyed_a_source_codes(source_codes)
    probe_registry = build_keyed_a_probe_registry()
    effective_env = keyed_a_env_with_secret_aliases(env if env is not None else os.environ)
    run_result = run_live_source_probes(
        session,
        source_codes=selected_sources,
        validation_run_key=validation_run_key,
        probe_registry=probe_registry,
        env=effective_env,
    )
    records = collect_keyed_a_records_for_run(session, run_key=run_result.validation_run_key)
    artifact_path = write_keyed_a_validation_artifact(
        output_path=artifact_output_path if artifact_output_path is not None else default_keyed_a_artifact_path(),
        run_result=run_result,
        source_records=records,
    )
    return run_result, artifact_path

