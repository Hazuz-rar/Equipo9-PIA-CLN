"""US-09/US-13/US-15: salida con folio liquidado y habitación sucia."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from src.application.reception.operations import OperationalCheckOutService
from src.domain.folios.entities import Folio, FolioStatus
from src.domain.folios.value_objects import (
    ChargeAmount, FolioId, PaymentAmount, ReservationReference,
)
from src.domain.reservations.entities import ReservationStatus
from src.domain.rooms.entities import Room, RoomStatus
from src.domain.rooms.value_objects import Capacity, Money, RoomNumber
from src.infrastructure.check_in_unit_of_work import SQLAlchemyCheckInUnitOfWork
from src.infrastructure.database.models.folio_model import FolioModel
from src.infrastructure.repositories.sqlalchemy_folio_repository import SQLAlchemyFolioRepository
from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
from tests.integration.test_operational_check_in import (
    AT_CHECKIN, KEY, ZONE, engine, prepare, service, state,
)

AT_CHECKOUT = datetime(2026, 12, 13, 12, tzinfo=ZONE)


def checkout(engine):
    return OperationalCheckOutService(
        lambda: SQLAlchemyCheckInUnitOfWork(lambda: Session(engine), KEY),
        ZONE,
    )


def checked_in(engine):
    rid, roomid = prepare(engine)
    service(engine).execute(rid, AT_CHECKIN)
    return rid, roomid


def test_success_closes_folio_and_marks_room_dirty(engine):
    rid, roomid = checked_in(engine)
    result = checkout(engine).execute(rid, AT_CHECKOUT)
    rs, rm, folios = state(engine, rid, roomid)
    assert result.reservation_id == rid
    assert result.room_id == roomid
    assert result.folio_id == folios[0].id
    assert rs == ReservationStatus.CHECK_OUT
    assert rm == RoomStatus.DIRTY
    assert folios[0].status == FolioStatus.CLOSED


def test_with_settled_charges_can_checkout(engine):
    rid, roomid = checked_in(engine)
    with Session(engine) as s:
        repo = SQLAlchemyFolioRepository(s)
        folio = repo.get_by_reservation_id(rid)
        folio.add_charge("Cargo demo", ChargeAmount(Decimal("250")))
        folio.add_payment("Pago demo", PaymentAmount(Decimal("250")))
        repo.update(folio)
        s.commit()
    checkout(engine).execute(rid, AT_CHECKOUT)
    assert state(engine, rid, roomid)[2][0].status == FolioStatus.CLOSED


def test_unpaid_balance_blocks_checkout(engine):
    rid, roomid = checked_in(engine)
    with Session(engine) as s:
        repo = SQLAlchemyFolioRepository(s)
        folio = repo.get_by_reservation_id(rid)
        folio.add_charge("Pendiente", ChargeAmount(Decimal("251")))
        repo.update(folio)
        s.commit()
    with pytest.raises(ValueError, match="liquidarse"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    rs, rm, folios = state(engine, rid, roomid)
    assert rs == ReservationStatus.CHECK_IN
    assert rm == RoomStatus.OCCUPIED
    assert folios[0].status == FolioStatus.OPEN


def test_no_folio_blocks_checkout(engine):
    rid, roomid = checked_in(engine)
    with Session(engine) as s:
        folio = s.query(FolioModel).filter_by(reservation_id=rid).one()
        s.delete(folio)
        s.commit()
    with pytest.raises(ValueError, match="no tiene folio"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    assert state(engine, rid, roomid)[0] == ReservationStatus.CHECK_IN


def test_closed_folio_blocks_checkout(engine):
    rid, roomid = checked_in(engine)
    with Session(engine) as s:
        repo = SQLAlchemyFolioRepository(s)
        folio = repo.get_by_reservation_id(rid)
        folio.close()
        repo.update(folio)
        s.commit()
    with pytest.raises(ValueError, match="ya está cerrado"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    assert state(engine, rid, roomid)[1] == RoomStatus.OCCUPIED


def test_wrong_date_blocks_early_departure(engine):
    rid, roomid = checked_in(engine)
    with pytest.raises(ValueError, match="fecha distinta"):
        checkout(engine).execute(rid, AT_CHECKOUT - timedelta(days=1))
    assert state(engine, rid, roomid)[0] == ReservationStatus.CHECK_IN


def test_wrong_date_blocks_delayed_departure(engine):
    rid, _ = checked_in(engine)
    with pytest.raises(ValueError, match="fecha distinta"):
        checkout(engine).execute(rid, AT_CHECKOUT + timedelta(days=1))


def test_late_checkout_after_two_is_blocked_without_charge(engine):
    rid, roomid = checked_in(engine)
    at = AT_CHECKOUT.replace(hour=14, minute=1)
    with pytest.raises(ValueError, match="late check-out"):
        checkout(engine).execute(rid, at)
    assert state(engine, rid, roomid)[0] == ReservationStatus.CHECK_IN


def test_two_oclock_is_within_free_tolerance(engine):
    rid, roomid = checked_in(engine)
    checkout(engine).execute(rid, AT_CHECKOUT.replace(hour=14))
    assert state(engine, rid, roomid)[1] == RoomStatus.DIRTY


def test_timezone_conversion(engine):
    rid, roomid = checked_in(engine)
    checkout(engine).execute(rid, AT_CHECKOUT.astimezone(timezone.utc))
    assert state(engine, rid, roomid)[0] == ReservationStatus.CHECK_OUT


def test_prevents_double_checkout(engine):
    rid, roomid = checked_in(engine)
    checkout(engine).execute(rid, AT_CHECKOUT)
    with pytest.raises(ValueError, match="con check-in"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    assert state(engine, rid, roomid)[1] == RoomStatus.DIRTY


def test_reservation_without_checkin_blocks_checkout(engine):
    rid, roomid = prepare(engine)
    with pytest.raises(ValueError, match="con check-in"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    assert state(engine, rid, roomid)[1] == RoomStatus.AVAILABLE


def test_missing_reservation(engine):
    with pytest.raises(ValueError, match="no existe"):
        checkout(engine).execute(uuid4(), AT_CHECKOUT)


def test_requires_datetime_with_timezone(engine):
    with pytest.raises(ValueError, match="zona horaria del hotel"):
        OperationalCheckOutService(lambda: None, None)
    rid, roomid = checked_in(engine)
    with pytest.raises(ValueError, match="zona horaria"):
        checkout(engine).execute(rid, datetime(2026, 12, 13, 12))
    assert state(engine, rid, roomid)[1] == RoomStatus.OCCUPIED


def test_dirty_room_can_be_cleaned_and_released(engine):
    rid, roomid = checked_in(engine)
    checkout(engine).execute(rid, AT_CHECKOUT)
    with Session(engine) as s:
        repo = SQLAlchemyRoomRepository(s)
        from src.domain.reservations.value_objects import RoomId
        room = repo.get_for_update(RoomId(roomid))
        assert room.can_accept_reservation() is False
        room.mark_clean()
        repo.update(RoomId(roomid), room)
        s.commit()
    assert state(engine, rid, roomid)[1] == RoomStatus.AVAILABLE


def test_room_transitions_reject_wrong_state():
    room = Room(RoomNumber("R1"), "Estándar", Capacity(2), Money(Decimal("100")))
    with pytest.raises(ValueError, match="ocupada"):
        room.mark_dirty()
    with pytest.raises(ValueError, match="sucia"):
        room.mark_clean()
    room.mark_occupied()
    room.mark_dirty()
    with pytest.raises(ValueError, match="ocupada"):
        room.mark_dirty()
    room.mark_clean()
    assert room.status == RoomStatus.AVAILABLE


def test_db_rolls_back_both_states_if_final_update_fails(engine, monkeypatch):
    rid, roomid = checked_in(engine)
    original = SQLAlchemyRoomRepository.update

    def fail_after_update(self, room_id, room):
        original(self, room_id, room)
        raise RuntimeError("Fallo al final de la transacción")

    monkeypatch.setattr(SQLAlchemyRoomRepository, "update", fail_after_update)
    with pytest.raises(RuntimeError, match="Fallo al final"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    rs, rm, folios = state(engine, rid, roomid)
    assert rs == ReservationStatus.CHECK_IN
    assert rm == RoomStatus.OCCUPIED
    assert folios[0].status == FolioStatus.OPEN


def test_rejects_multiple_historical_folios(engine):
    rid, roomid = checked_in(engine)
    with Session(engine) as s:
        SQLAlchemyFolioRepository(s).add(Folio(FolioId(uuid4()), ReservationReference(rid)))
        s.commit()
    with pytest.raises(ValueError, match="varios folios"):
        checkout(engine).execute(rid, AT_CHECKOUT)
    assert state(engine, rid, roomid)[0] == ReservationStatus.CHECK_IN
