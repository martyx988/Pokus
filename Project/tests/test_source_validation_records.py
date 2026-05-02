from __future__ import annotations

import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain import Base
from pokus_backend.domain.source_validation_models import SourceValidationRecord
from pokus_backend.validation.source_validation_records import (
    SourceValidationRecordInput,
    get_source_validation_record,
    list_source_validation_records_for_run,
    persist_source_validation_record,
)


class SourceValidationRecordPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_persists_and_reads_back_record_keyed_by_run_and_source(self) -> None:
        created = persist_source_validation_record(
            self.session,
            SourceValidationRecordInput(
                validation_run_key="m3.1-live-2026-05-02",
                source_code="fmp",
                is_available=True,
                auth_required=True,
                quota_rate_limit_notes="Free tier 250 calls/day.",
                speed_notes="Median 430ms over 20 probe requests.",
                exchange_coverage_notes="Strong NYSE/NASDAQ, partial PSE.",
                observed_latency_ms=430,
                classification_verdict="promote",
                assigned_role="primary_discovery",
            ),
        )
        self.session.commit()

        stored = get_source_validation_record(
            self.session,
            validation_run_key="m3.1-live-2026-05-02",
            source_code="FMP",
        )
        assert stored is not None
        self.assertEqual(stored.id, created.id)
        self.assertEqual(stored.source_code, "FMP")
        self.assertEqual(stored.classification_verdict, "promote")
        self.assertEqual(stored.assigned_role, "primary_discovery")
        self.assertEqual(stored.observed_latency_ms, 430)

    def test_supports_all_milestone_verdict_values(self) -> None:
        verdicts = [
            "promote",
            "fallback_only",
            "validation_only",
            "not_for_universe_loader",
            "reject",
        ]
        for index, verdict in enumerate(verdicts, start=1):
            persist_source_validation_record(
                self.session,
                SourceValidationRecordInput(
                    validation_run_key="m3.1-all-verdicts",
                    source_code=f"SRC{index}",
                    is_available=(index % 2 == 0),
                    auth_required=(index % 2 == 1),
                    quota_rate_limit_notes="Observed and captured.",
                    speed_notes="Observed and captured.",
                    exchange_coverage_notes="Observed and captured.",
                    classification_verdict=verdict,
                    assigned_role="validation_only" if verdict != "reject" else None,
                ),
            )
        self.session.commit()

        rows = list_source_validation_records_for_run(self.session, validation_run_key="m3.1-all-verdicts")
        self.assertEqual(len(rows), len(verdicts))
        self.assertSetEqual({row.classification_verdict for row in rows}, set(verdicts))

    def test_rejects_invalid_classification_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "classification_verdict must be one of"):
            persist_source_validation_record(
                self.session,
                SourceValidationRecordInput(
                    validation_run_key="m3.1-invalid",
                    source_code="YF",
                    is_available=True,
                    auth_required=False,
                    quota_rate_limit_notes="None observed.",
                    speed_notes="Good.",
                    exchange_coverage_notes="NYSE only.",
                    classification_verdict="fallback only",
                ),
            )

    def test_requires_evidence_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "quota_rate_limit_notes must be a non-empty string"):
            persist_source_validation_record(
                self.session,
                SourceValidationRecordInput(
                    validation_run_key="m3.1-missing-evidence",
                    source_code="AKSHARE",
                    is_available=False,
                    auth_required=False,
                    quota_rate_limit_notes="  ",
                    speed_notes="Unavailable",
                    exchange_coverage_notes="Unavailable",
                    classification_verdict="reject",
                ),
            )

    def test_upserts_existing_run_source_record(self) -> None:
        first = persist_source_validation_record(
            self.session,
            SourceValidationRecordInput(
                validation_run_key="m3.1-upsert",
                source_code="stooq",
                is_available=True,
                auth_required=False,
                quota_rate_limit_notes="No auth key needed.",
                speed_notes="Median 800ms.",
                exchange_coverage_notes="NYSE/NASDAQ partial PSE.",
                classification_verdict="fallback_only",
                assigned_role="fallback_discovery",
            ),
        )
        self.session.commit()

        second = persist_source_validation_record(
            self.session,
            SourceValidationRecordInput(
                validation_run_key="m3.1-upsert",
                source_code="STOOQ",
                is_available=False,
                auth_required=False,
                quota_rate_limit_notes="Rate limited under burst load.",
                speed_notes="Median 1200ms.",
                exchange_coverage_notes="Mostly delayed for PSE.",
                classification_verdict="validation_only",
                assigned_role="validation_only",
            ),
        )
        self.session.commit()

        self.assertEqual(first.id, second.id)
        count = self.session.scalar(
            select(SourceValidationRecord).where(
                SourceValidationRecord.validation_run_key == "m3.1-upsert",
                SourceValidationRecord.source_code == "STOOQ",
            )
        )
        assert count is not None
        self.assertEqual(self.session.query(SourceValidationRecord).count(), 1)
        self.assertEqual(count.classification_verdict, "validation_only")
        self.assertEqual(count.assigned_role, "validation_only")

    def test_database_constraint_rejects_invalid_verdict_when_bypassing_helper(self) -> None:
        self.session.add(
            SourceValidationRecord(
                validation_run_key="m3.1-db-constraint",
                source_code="DIRECT",
                is_available=True,
                auth_required=False,
                quota_rate_limit_notes="Captured.",
                speed_notes="Captured.",
                exchange_coverage_notes="Captured.",
                observed_latency_ms=50,
                classification_verdict="invalid_value",
                assigned_role=None,
                recorded_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()


if __name__ == "__main__":
    unittest.main()
