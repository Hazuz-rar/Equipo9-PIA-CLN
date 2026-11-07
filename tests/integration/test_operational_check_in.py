"""Pruebas de recepción transaccional con SQLite (no validan concurrencia PG)."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.application.reception.operations import OperationalCheckInService
from src.domain.folios.entities import Folio, FolioStatus
from src.domain.folios.value_objects import FolioId, ReservationReference
from src.domain.reception.check_in import GuestCheckInRegistration
from src.domain.reservations.entities import ReservationStatus
from src.domain.rooms.entities import RoomStatus
from src.infrastructure.check_in_unit_of_work import SQLAlchemyCheckInUnitOfWork
from src.infrastructure.database.base import Base
from src.infrastructure.database import models  # noqa: F401
from src.infrastructure.database.models.reservation_model import ReservationModel
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.models.folio_model import FolioModel
from src.infrastructure.repositories.sqlalchemy_check_in_repository import (
    SQLAlchemyCheckInRepository,
)
from src.infrastructure.repositories.sqlalchemy_folio_repository import (
    SQLAlchemyFolioRepository,
)

ZONE = timezone(timedelta(hours=-6))  # Solo ejemplo de prueba; no zona oficial.
KEY = Fernet.generate_key().decode("ascii")
AT_CHECKIN = datetime(2026, 12, 10, 15, 0, tzinfo=ZONE)


@pytest.fixture
def engine():
    db = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(db, "connect")
    def foreign_keys(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    yield db
    db.dispose()


def make_registration(*, guarantee=True, registered_at=None, valid_until=None):
    return GuestCheckInRegistration(
        full_name="Cliente ficticio",
        official_id_number="FICTICIO-1001",
        official_id_valid_until=valid_until or date(2027, 1, 1),
        nationality="Mexicana",
        contact_details="contacto ficticio",
        invoice_requested=False,
        fiscal_address=None,
        guarantee_accepted=guarantee,
        registered_at=registered_at or AT_CHECKIN,
    )


def prepare(engine, *, status=ReservationStatus.CONFIRMED,
            room_status=RoomStatus.AVAILABLE, registered=True,
            guarantee=True, with_room=True, valid_until=None,
            registered_at=None, existing_folio=False, closed_folio=False):
    rid, roomid = uuid4(), uuid4()
    with Session(engine) as session:
        if with_room:
            session.add(RoomModel(
                id=roomid, number="D-101", room_type="Estándar",
                capacity=2, base_rate=1250, status=room_status,
            ))
        session.add(ReservationModel(
            id=rid, guest_id=uuid4(), room_id=roomid,
            check_in=date(2026, 12, 10), check_out=date(2026, 12, 13),
            status=status,
        ))
        session.flush()
        if registered:
            SQLAlchemyCheckInRepository(session, KEY).add(
                rid, make_registration(
                    guarantee=guarantee,
                    valid_until=valid_until,
                    registered_at=registered_at,
                )
            )
        if existing_folio:
            folio = Folio(id=FolioId(uuid4()), reservation_id=ReservationReference(rid))
            if closed_folio:
                folio.close()
            SQLAlchemyFolioRepository(session).add(folio)
        session.commit()
    return rid, roomid


def service(engine):
    return OperationalCheckInService(
        lambda: SQLAlchemyCheckInUnitOfWork(lambda: Session(engine), KEY),
        ZONE,
    )


def state(engine, rid, roomid):
    with Session(engine) as s:
        reservation = s.get(ReservationModel, rid)
        room = s.get(RoomModel, roomid)
        folios = list(s.scalars(select(FolioModel).where(FolioModel.reservation_id == rid)))
        return reservation.status, room.status if room else None, folios


def test_check_in_updates_reservation_room_and_creates_folio(engine):
    rid, roomid = prepare(engine)
    outcome = service(engine).execute(rid, AT_CHECKIN)
    rs, rm, folios = state(engine, rid, roomid)
    assert outcome.reservation_id == rid
    assert outcome.room_id == roomid
    assert rs == ReservationStatus.CHECK_IN
    assert rm == RoomStatus.OCCUPIED
    assert len(folios) == 1
    assert folios[0].id == outcome.folio_id
    assert folios[0].status == FolioStatus.OPEN


def test_reuses_existing_open_folio(engine):
    rid, roomid = prepare(engine, existing_folio=True)
    with Session(engine) as s:
        initial = s.scalar(select(FolioModel).where(FolioModel.reservation_id == rid)).id
    outcome = service(engine).execute(rid, AT_CHECKIN)
    assert outcome.folio_id == initial
    assert len(state(engine, rid, roomid)[2]) == 1


def test_missing_registration_blocks_check_in(engine):
    rid, roomid = prepare(engine, registered=False)
    with pytest.raises(ValueError, match="documentación obligatoria"):
        service(engine).execute(rid, AT_CHECKIN)
    rs, rm, folios = state(engine, rid, roomid)
    assert rs == ReservationStatus.CONFIRMED
    assert rm == RoomStatus.AVAILABLE
    assert folios == []


def test_missing_guarantee_blocks_opening_folio(engine):
    rid, roomid = prepare(engine, guarantee=False)
    with pytest.raises(ValueError, match="Falta garantía válida"):
        service(engine).execute(rid, AT_CHECKIN)
    rs, rm, folios = state(engine, rid, roomid)
    assert rs == ReservationStatus.CONFIRMED
    assert rm == RoomStatus.AVAILABLE
    assert folios == []


def test_before_3pm_is_not_enabled_without_cleanliness(engine):
    rid, roomid = prepare(engine)
    with pytest.raises(ValueError, match="early check-in"):
        service(engine).execute(rid, AT_CHECKIN - timedelta(minutes=1))
    assert state(engine, rid, roomid)[0] == ReservationStatus.CONFIRMED


def test_rejects_wrong_arrival_day(engine):
    rid, roomid = prepare(engine)
    with pytest.raises(ValueError, match="día de llegada"):
        service(engine).execute(rid, AT_CHECKIN + timedelta(days=1))
    assert state(engine, rid, roomid)[1] == RoomStatus.AVAILABLE


def test_rejects_expired_id_at_check_in(engine):
    rid, roomid = prepare(engine,
        registered_at=AT_CHECKIN - timedelta(days=10),
        valid_until=date(2026, 12, 5),
    )
    with pytest.raises(ValueError, match="identificación oficial está vencida"):
        service(engine).execute(rid, AT_CHECKIN)
    assert state(engine, rid, roomid)[0] == ReservationStatus.CONFIRMED


def test_rejects_room_out_of_order(engine):
    rid, roomid = prepare(engine, room_status=RoomStatus.OUT_OF_ORDER)
    with pytest.raises(ValueError, match="habitación no está disponible"):
        service(engine).execute(rid, AT_CHECKIN)
    assert state(engine, rid, roomid)[0] == ReservationStatus.CONFIRMED


def test_rejects_non_confirmed_reservation(engine):
    rid, roomid = prepare(engine, status=ReservationStatus.REQUESTED)
    with pytest.raises(ValueError, match="reserva confirmada"):
        service(engine).execute(rid, AT_CHECKIN)
    assert state(engine, rid, roomid)[1] == RoomStatus.AVAILABLE


def test_double_check_in_does_not_add_another_folio(engine):
    rid, roomid = prepare(engine)
    service(engine).execute(rid, AT_CHECKIN)
    with pytest.raises(ValueError, match="reserva confirmada"):
        service(engine).execute(rid, AT_CHECKIN)
    assert len(state(engine, rid, roomid)[2]) == 1


def test_rollback_restores_both_states_if_folio_creation_fails(engine, monkeypatch):
    rid, roomid = prepare(engine)
    original = SQLAlchemyFolioRepository.add

    def fail_after_flush(self, folio):
        original(self, folio)
        raise RuntimeError("Fallo después del insert")

    monkeypatch.setattr(SQLAlchemyFolioRepository, "add", fail_after_flush)
    with pytest.raises(RuntimeError, match="Fallo después"):
        service(engine).execute(rid, AT_CHECKIN)
    rs, rm, folios = state(engine, rid, roomid)
    assert rs == ReservationStatus.CONFIRMED
    assert rm == RoomStatus.AVAILABLE
    assert folios == []


def test_cannot_reuse_closed_folio(engine):
    rid, roomid = prepare(engine, existing_folio=True, closed_folio=True)
    with pytest.raises(ValueError, match="folio cerrado"):
        service(engine).execute(rid, AT_CHECKIN)
    assert state(engine, rid, roomid)[0] == ReservationStatus.CONFIRMED


def test_requires_explicit_local_timezone(engine):
    with pytest.raises(ValueError, match="zona horaria del hotel"):
        OperationalCheckInService(
            lambda: SQLAlchemyCheckInUnitOfWork(lambda: Session(engine), KEY),
            None,
        )
    rid, roomid = prepare(engine)
    with pytest.raises(ValueError, match="zona horaria"):
        service(engine).execute(rid, datetime(2026, 12, 10, 15))
    assert state(engine, rid, roomid)[0] == ReservationStatus.CONFIRMED


def test_timezone_conversion_at_standard_checkin(engine):
    rid, roomid = prepare(engine)
    result = service(engine).execute(rid, AT_CHECKIN.astimezone(timezone.utc))
    assert result.reservation_id == rid
