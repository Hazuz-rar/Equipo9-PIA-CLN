
"""Pruebas de persistencia de folios con SQLite efímero."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.domain.folios.entities import Folio, FolioStatus
from src.domain.folios.value_objects import (
    ChargeAmount,
    FolioId,
    PaymentAmount,
    ReservationReference,
)
from src.domain.reservations.entities import ReservationStatus
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import ReservationModel
from src.infrastructure.repositories.sqlalchemy_folio_repository import (
    SQLAlchemyFolioRepository,
)


@pytest.fixture
def engine():
    db = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(db, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    yield db
    db.dispose()


def seed_reservation(session):
    reservation_id = uuid4()

    session.add(
        ReservationModel(
            id=reservation_id,
            guest_id=uuid4(),
            room_id=uuid4(),
            check_in=date(2026, 12, 10),
            check_out=date(2026, 12, 13),
            status=ReservationStatus.CONFIRMED,
        )
    )

    session.flush()
    return reservation_id


def make_folio(reservation_id):
    return Folio(
        id=FolioId(uuid4()),
        reservation_id=ReservationReference(reservation_id),
    )


def test_persists_and_reads_folio_in_another_session(engine):
    with Session(engine) as session:
        reservation_id = seed_reservation(session)
        folio = make_folio(reservation_id)
        SQLAlchemyFolioRepository(session).add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        recovered = SQLAlchemyFolioRepository(
            session
        ).get_by_id(folio_id)

        assert recovered.id == folio_id
        assert recovered.reservation_id.value == reservation_id
        assert recovered.status == FolioStatus.OPEN
        assert recovered.balance == Decimal("0")


def test_appends_charges_and_payments_without_duplicates(engine):
    with Session(engine) as session:
        reservation_id = seed_reservation(session)
        folio = make_folio(reservation_id)
        folio.add_charge(
            "Hospedaje", ChargeAmount(Decimal("2500.00"))
        )

        SQLAlchemyFolioRepository(session).add(folio)
        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        recovered = repo.get_by_id(folio_id)

        recovered.add_charge(
            "Restaurante", ChargeAmount(Decimal("200.00"))
        )
        recovered.add_payment(
            "Pago parcial", PaymentAmount(Decimal("1000.00"))
        )

        repo.update(recovered)
        session.commit()

    with Session(engine) as session:
        recovered = SQLAlchemyFolioRepository(
            session
        ).get_by_id(folio_id)

        assert len(recovered.charges) == 2
        assert len(recovered.payments) == 1
        assert recovered.total_charges == Decimal("2700.00")
        assert recovered.total_payments == Decimal("1000.00")
        assert recovered.balance == Decimal("1700.00")


def test_close_folio_is_persistent(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)

        folio.add_charge(
            "Hospedaje", ChargeAmount(Decimal("100"))
        )
        folio.add_payment(
            "Pago", PaymentAmount(Decimal("100"))
        )

        repo = SQLAlchemyFolioRepository(session)
        repo.add(folio)
        folio.close()
        repo.update(folio)

        session.commit()
        folio_id = folio.id

    with Session(engine) as session:
        restored = SQLAlchemyFolioRepository(
            session
        ).get_by_id(folio_id)

        assert restored.status == FolioStatus.CLOSED
        assert restored.balance == Decimal("0")

        with pytest.raises(ValueError, match="folio cerrado"):
            restored.add_charge(
                "Extra", ChargeAmount(Decimal("5"))
            )


def test_missing_folio_returns_none(engine):
    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        assert repo.get_by_id(FolioId(uuid4())) is None


def test_must_not_rewrite_persisted_charges(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        folio = make_folio(rid)
        folio.add_charge(
            "Hospedaje", ChargeAmount(Decimal("500"))
        )

        repo = SQLAlchemyFolioRepository(session)
        repo.add(folio)
        session.commit()

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        recovered = repo.get_by_id(folio.id)

        recovered.charges[0].description = "Cambio indebido"

        with pytest.raises(
            ValueError, match="modificarse movimientos"
        ):
            repo.update(recovered)


def test_rollback_reverts_folio_and_movements(engine):
    with Session(engine) as session:
        rid = seed_reservation(session)
        session.commit()

    with Session(engine) as session:
        folio = make_folio(rid)
        folio.add_charge(
            "Hospedaje", ChargeAmount(Decimal("100"))
        )

        SQLAlchemyFolioRepository(session).add(folio)
        session.rollback()

    with Session(engine) as session:
        repo = SQLAlchemyFolioRepository(session)
        assert repo.get_by_id(folio.id) is None


def test_reservation_reference_has_foreign_key(engine):
    with Session(engine) as session:
        folio = make_folio(uuid4())

        with pytest.raises(Exception):
            SQLAlchemyFolioRepository(session).add(folio)

        session.rollback()
