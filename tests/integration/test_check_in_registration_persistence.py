
"""Registro cifrado sin API pública: RN-11, US-07, US-08."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.application.reception.services import (
    CheckInRegistrationService,
)
from src.domain.reception.check_in import (
    GuestCheckInRegistration,
)
from src.domain.reservations.entities import ReservationStatus
from src.infrastructure.database.base import Base
from src.infrastructure.database import models  # noqa: F401
from src.infrastructure.database.models.check_in_model import (
    CheckInRecordModel,
)
from src.infrastructure.database.models.reservation_model import (
    ReservationModel,
)
from src.infrastructure.repositories.sqlalchemy_reservation_repository import (
    SQLAlchemyReservationRepository,
)
from src.infrastructure.repositories.sqlalchemy_check_in_repository import (
    SQLAlchemyCheckInRepository,
)


KEY = Fernet.generate_key().decode("ascii")


@pytest.fixture
def engine():
    db = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(db, "connect")
    def fk_on(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    yield db
    db.dispose()


def seed(session, status=ReservationStatus.CONFIRMED):
    rid = uuid4()

    session.add(
        ReservationModel(
            id=rid,
            guest_id=uuid4(),
            room_id=uuid4(),
            check_in=date(2026, 12, 10),
            check_out=date(2026, 12, 13),
            status=status,
        )
    )
    session.flush()
    return rid


def record(guarantee=True):
    return GuestCheckInRegistration(
        full_name="Huésped confidencial",
        official_id_number="DOCUMENTO-SECRETO-123",
        official_id_valid_until=date(2027, 1, 1),
        nationality="Mexicana",
        contact_details="contacto confidencial",
        invoice_requested=False,
        fiscal_address=None,
        guarantee_accepted=guarantee,
        registered_at=datetime(
            2026, 12, 10, 15,
            tzinfo=timezone(timedelta(hours=-6)),
        ),
    )


def service(session, key=KEY):
    return CheckInRegistrationService(
        SQLAlchemyReservationRepository(session),
        SQLAlchemyCheckInRepository(session, key),
    )


def test_encrypt_and_restore(engine):
    with Session(engine) as session:
        rid = seed(session)
        assert service(session).register(rid, record()) is False

        stored = session.get(CheckInRecordModel, rid)

        assert b"DOCUMENTO-SECRETO" not in stored.encrypted_payload
        assert b"confidencial" not in stored.encrypted_payload
        assert stored.guarantee_accepted is True

        session.commit()

    with Session(engine) as session:
        restored = SQLAlchemyCheckInRepository(
            session, KEY
        ).get_by_reservation_id(rid)

        assert restored.official_id_number == "DOCUMENTO-SECRETO-123"
        assert restored.registered_at.utcoffset() == timedelta(hours=-6)


def test_records_missing_guarantee_risk(engine):
    with Session(engine) as session:
        rid = seed(session)

        assert service(session).register(
            rid, record(False)
        ) is True

        stored = session.get(CheckInRecordModel, rid)
        assert stored.missing_guarantee_risk is True

        session.commit()


def test_reject_unconfirmed_reservation(engine):
    with Session(engine) as session:
        rid = seed(session, ReservationStatus.REQUESTED)

        with pytest.raises(ValueError, match="confirmada"):
            service(session).register(rid, record())


def test_reject_missing_reservation(engine):
    with Session(engine) as session:
        with pytest.raises(ValueError, match="no existe"):
            service(session).register(uuid4(), record())


def test_reject_duplicate_registration(engine):
    with Session(engine) as session:
        rid = seed(session)
        service(session).register(rid, record())

        with pytest.raises(ValueError, match="ya fue registrada"):
            service(session).register(rid, record())


def test_rollback_reverts_registration(engine):
    with Session(engine) as session:
        rid = seed(session)
        session.commit()

    with Session(engine) as session:
        service(session).register(rid, record())
        session.rollback()

    with Session(engine) as session:
        assert SQLAlchemyCheckInRepository(
            session, KEY
        ).get_by_reservation_id(rid) is None


def test_wrong_key_cannot_decrypt(engine):
    with Session(engine) as session:
        rid = seed(session)
        service(session).register(rid, record())
        session.commit()

    with Session(engine) as session:
        wrong_key = Fernet.generate_key().decode("ascii")

        with pytest.raises(InvalidToken):
            SQLAlchemyCheckInRepository(
                session, wrong_key
            ).get_by_reservation_id(rid)


def test_duplicate_primary_key_protected_by_db(engine):
    with Session(engine) as session:
        rid = seed(session)
        service(session).register(rid, record())

        with pytest.raises(IntegrityError):
            SQLAlchemyCheckInRepository(
                session, KEY
            ).add(rid, record())

        session.rollback()


def test_registration_does_not_change_reservation(engine):
    with Session(engine) as session:
        rid = seed(session)
        service(session).register(rid, record())

        assert (
            session.get(ReservationModel, rid).status
            == ReservationStatus.CONFIRMED
        )


def test_registration_with_accepted_guarantee_is_not_checkin(engine):
    with Session(engine) as session:
        rid = seed(session)
        service(session).register(rid, record(True))

        assert (
            session.get(ReservationModel, rid).status
            != ReservationStatus.CHECK_IN
        )
