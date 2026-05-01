from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pokus_backend.domain.reference_models import Base, Exchange, InstrumentType


class ReferenceModelsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_exchange_creation_supports_launch_and_future_cry(self) -> None:
        self.session.add_all(
            [
                Exchange(code="NYSE", name="New York Stock Exchange", is_launch_active=True),
                Exchange(code="CRY", name="Synthetic Crypto Exchange", is_launch_active=False),
            ]
        )
        self.session.commit()

        rows = self.session.query(Exchange).order_by(Exchange.code.asc()).all()
        self.assertEqual([row.code for row in rows], ["CRY", "NYSE"])
        self.assertFalse(rows[0].is_launch_active)
        self.assertTrue(rows[1].is_launch_active)

    def test_duplicate_exchange_code_is_rejected(self) -> None:
        self.session.add(Exchange(code="NASDAQ", name="Nasdaq", is_launch_active=True))
        self.session.commit()

        self.session.add(Exchange(code="NASDAQ", name="Another Nasdaq", is_launch_active=False))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_instrument_type_duplicate_code_is_rejected(self) -> None:
        self.session.add(InstrumentType(code="ETF", name="ETF", is_launch_active=True))
        self.session.commit()

        self.session.add(InstrumentType(code="ETF", name="Different ETF", is_launch_active=False))
        with self.assertRaises(IntegrityError):
            self.session.commit()
        self.session.rollback()

    def test_crypto_instrument_type_is_representable_without_launch_activation(self) -> None:
        crypto = InstrumentType(code="CRYPTO", name="Crypto", is_launch_active=False)
        self.session.add(crypto)
        self.session.commit()

        stored = self.session.query(InstrumentType).filter_by(code="CRYPTO").one()
        self.assertEqual(stored.name, "Crypto")
        self.assertFalse(stored.is_launch_active)


if __name__ == "__main__":
    unittest.main()
