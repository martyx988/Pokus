from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_baseline import (
    LAUNCH_EXCHANGES,
    LAUNCH_INSTRUMENT_TYPES,
    seed_launch_baseline_records,
)
from pokus_backend.domain.reference_models import Base, Exchange, InstrumentType


class ReferenceBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp_dir.name) / "reference-baseline.sqlite3"
        self.db_url = f"sqlite+pysqlite:///{self.db_path.as_posix()}"
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self._tmp_dir.cleanup()

    def test_seed_creates_exact_launch_baseline_records(self) -> None:
        seed_launch_baseline_records(self.db_url)

        with Session(self.engine) as session:
            exchanges = session.scalars(select(Exchange).order_by(Exchange.code.asc())).all()
            instrument_types = session.scalars(select(InstrumentType).order_by(InstrumentType.code.asc())).all()

        self.assertEqual(
            [(row.code, row.name, row.is_launch_active) for row in exchanges],
            sorted([(code, name, True) for code, name in LAUNCH_EXCHANGES]),
        )
        self.assertEqual(
            [(row.code, row.name, row.is_launch_active) for row in instrument_types],
            sorted([(code, name, True) for code, name in LAUNCH_INSTRUMENT_TYPES]),
        )

    def test_seed_is_idempotent_across_repeated_runs(self) -> None:
        seed_launch_baseline_records(self.db_url)
        seed_launch_baseline_records(self.db_url)

        with Session(self.engine) as session:
            exchange_count = session.query(Exchange).count()
            instrument_type_count = session.query(InstrumentType).count()

        self.assertEqual(exchange_count, len(LAUNCH_EXCHANGES))
        self.assertEqual(instrument_type_count, len(LAUNCH_INSTRUMENT_TYPES))


if __name__ == "__main__":
    unittest.main()
