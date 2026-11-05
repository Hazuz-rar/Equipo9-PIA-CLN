
"""Pruebas de persistencia de vales RN-12."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.domain.folios.vouchers import ChargeVoucher
from src.domain.folios.value_objects import ChargeAmount
from src.infrastructure.repositories.sqlalchemy_folio_repository import (
    SQLAlchemyFolioRepository,
)
from tests.integration.test_folio_repository import (
    engine,
    make_folio,
    seed_reservation,
)


def make_voucher(**changes):
    values = {
        "room_number": "120",
        "guest_name": "Huésped de prueba",
        "guest_signature": "referencia-firma-prueba",
        "issued_at": datetime(
            2026, 12, 11, 18, 0,
            tzinfo=timezone(timedelta(hours=-6)),
        ),
        "point_of_sale": "Restaurante",
        "consumption_detail": "Cena de prueba",
        "amount": Decimal("350.00"),
        "voucher_number": "V-120-001",
    }

    values.update(changes)
    return ChargeVoucher(**values)


def test_voucher_persisted_and_read_across_sessions(engine):
    voucher = make_voucher()

    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)
        folio.add_voucher_charge(voucher)

        SQLAlchemyFolioRepository(session).add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        recovered = SQLAlchemyFolioRepository(
            session
        ).get_by_id(folio_id)

        assert len(recovered.charges) == 1

        restored = recovered.charges[0].voucher

        assert restored is not None
        assert restored.voucher_number == voucher.voucher_number
        assert restored.guest_name == voucher.guest_name
        assert restored.issued_at == voucher.issued_at
        assert recovered.balance == Decimal("350.00")


def test_legacy_charge_without_voucher_remains_readable(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)

        folio.add_charge(
            "Hospedaje histórico",
            ChargeAmount(Decimal("100.00")),
        )

        SQLAlchemyFolioRepository(session).add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        restored = SQLAlchemyFolioRepository(
            session
        ).get_by_id(folio_id)

        assert restored.charges[0].voucher is None
        assert restored.total_charges == Decimal("100.00")


def test_cannot_modify_registered_voucher(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)
        folio.add_voucher_charge(make_voucher())

        repo = SQLAlchemyFolioRepository(session)
        repo.add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        folio = repo.get_by_id(folio_id)

        folio.charges[0].voucher = make_voucher(
            voucher_number="ALTERADO"
        )

        with pytest.raises(
            ValueError,
            match="No pueden modificarse",
        ):
            repo.update(folio)


def test_invalid_difference_between_charge_and_voucher(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)

        with pytest.raises(
            ValueError,
            match="importe del cargo",
        ):
            folio.add_charge(
                "Cena de prueba",
                ChargeAmount(Decimal("300.00")),
                voucher=make_voucher(),
            )

        assert len(folio.charges) == 0


def test_new_voucher_on_existing_folio(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)

        repo = SQLAlchemyFolioRepository(session)
        repo.add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        folio = repo.get_by_id(folio_id)

        folio.add_voucher_charge(make_voucher())
        repo.update(folio)
        session.commit()

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        folio = repo.get_by_id(folio_id)

        assert len(folio.charges) == 1
        assert folio.charges[0].voucher is not None


def test_rollback_does_not_persist_new_voucher(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)

        SQLAlchemyFolioRepository(session).add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        folio = repo.get_by_id(folio_id)

        folio.add_voucher_charge(make_voucher())
        repo.update(folio)
        session.rollback()

    with Session(engine) as session:
        restored = SQLAlchemyFolioRepository(
            session
        ).get_by_id(folio_id)

        assert restored.charges == []
