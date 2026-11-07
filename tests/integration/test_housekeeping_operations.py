"""US-14/US-15: limpieza, permiso lógico y auditoría transaccional."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.application.rooms.operations import HousekeepingService, HotelStaffRole
from src.domain.rooms.entities import RoomStatus
from src.domain.reservations.value_objects import StayPeriod, RoomId
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.models.room_cleaning_event_model import RoomCleaningEventModel
from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
from src.infrastructure.room_cleaning_unit_of_work import SQLAlchemyRoomCleaningUnitOfWork
from tests.integration.test_operational_check_in import engine


def create_room(engine, number="D-101", status=RoomStatus.DIRTY):
    room_id = uuid4()
    with Session(engine) as s:
        s.add(RoomModel(
            id=room_id, number=number, room_type="Estándar",
            capacity=2, base_rate=1250, status=status,
        ))
        s.commit()
    return room_id


def cleaning_service(engine):
    return HousekeepingService(
        lambda: SQLAlchemyRoomCleaningUnitOfWork(lambda: Session(engine))
    )


def room_status(engine, room_id):
    with Session(engine) as s:
        return s.get(RoomModel, room_id).status


def audits(engine):
    with Session(engine) as s:
        return list(s.scalars(select(RoomCleaningEventModel)))


def test_list_pending_only_dirty_rooms_sorted(engine):
    create_room(engine, "D-103", RoomStatus.AVAILABLE)
    create_room(engine, "D-102", RoomStatus.DIRTY)
    create_room(engine, "D-101", RoomStatus.DIRTY)
    pending = cleaning_service(engine).list_pending(HotelStaffRole.HOUSEKEEPING)
    assert [room.number for room in pending] == ["D-101", "D-102"]


def test_list_pending_empty_when_no_dirty(engine):
    create_room(engine, status=RoomStatus.AVAILABLE)
    assert cleaning_service(engine).list_pending(HotelStaffRole.HOUSEKEEPING) == []


@pytest.mark.parametrize("role", [
    HotelStaffRole.RECEPTION, HotelStaffRole.MANAGER_RECEPTION,
    HotelStaffRole.MANAGER_OPERATIONS, "HOUSEKEEPING", None,
])
def test_list_pending_rejects_other_roles(engine, role):
    with pytest.raises(PermissionError, match="rol de Limpieza"):
        cleaning_service(engine).list_pending(role)


def test_cleaning_updates_room_and_persists_actor_event(engine):
    room_id = create_room(engine)
    actor_id = uuid4()
    result = cleaning_service(engine).finish_cleaning(
        room_id, actor_id, HotelStaffRole.HOUSEKEEPING
    )
    assert result == RoomStatus.AVAILABLE
    assert room_status(engine, room_id) == RoomStatus.AVAILABLE
    event = audits(engine)[0]
    assert event.room_id == room_id
    assert event.actor_id == actor_id
    assert event.actor_role == "HOUSEKEEPING"
    assert event.previous_status == "DIRTY"
    assert event.new_status == "AVAILABLE"
    assert event.occurred_at is not None


def test_reception_cannot_clean(engine):
    room_id = create_room(engine)
    with pytest.raises(PermissionError, match="rol de Limpieza"):
        cleaning_service(engine).finish_cleaning(room_id, uuid4(), HotelStaffRole.RECEPTION)
    assert room_status(engine, room_id) == RoomStatus.DIRTY
    assert audits(engine) == []


def test_cleaning_nonexistent_room_rejected(engine):
    with pytest.raises(ValueError, match="no existe"):
        cleaning_service(engine).finish_cleaning(uuid4(), uuid4(), HotelStaffRole.HOUSEKEEPING)
    assert audits(engine) == []


@pytest.mark.parametrize("status", [RoomStatus.AVAILABLE, RoomStatus.OCCUPIED, RoomStatus.OUT_OF_ORDER])
def test_only_dirty_room_can_be_cleaned(engine, status):
    room_id = create_room(engine, status=status)
    with pytest.raises(ValueError, match="habitación sucia"):
        cleaning_service(engine).finish_cleaning(room_id, uuid4(), HotelStaffRole.HOUSEKEEPING)
    assert room_status(engine, room_id) == status
    assert audits(engine) == []


def test_double_clean_rejected_and_event_not_duplicated(engine):
    room_id = create_room(engine)
    worker = uuid4()
    service = cleaning_service(engine)
    service.finish_cleaning(room_id, worker, HotelStaffRole.HOUSEKEEPING)
    with pytest.raises(ValueError, match="habitación sucia"):
        service.finish_cleaning(room_id, worker, HotelStaffRole.HOUSEKEEPING)
    assert len(audits(engine)) == 1


def test_rollback_when_audit_fails(engine, monkeypatch):
    room_id = create_room(engine)
    from src.infrastructure.room_cleaning_unit_of_work import SQLAlchemyCleaningAuditRepository

    def fail_audit(self, **kwargs):
        raise RuntimeError("No se pudo auditar")

    monkeypatch.setattr(SQLAlchemyCleaningAuditRepository, "add_cleaning_event", fail_audit)
    with pytest.raises(RuntimeError, match="auditar"):
        cleaning_service(engine).finish_cleaning(
            room_id, uuid4(), HotelStaffRole.HOUSEKEEPING
        )
    assert room_status(engine, room_id) == RoomStatus.DIRTY
    assert audits(engine) == []


def test_rollback_when_room_update_fails(engine, monkeypatch):
    room_id = create_room(engine)
    original = SQLAlchemyRoomRepository.update

    def fail_update(self, rid, room):
        original(self, rid, room)
        raise RuntimeError("Fallo posterior a actualización")

    monkeypatch.setattr(SQLAlchemyRoomRepository, "update", fail_update)
    with pytest.raises(RuntimeError, match="Fallo posterior"):
        cleaning_service(engine).finish_cleaning(
            room_id, uuid4(), HotelStaffRole.HOUSEKEEPING
        )
    assert room_status(engine, room_id) == RoomStatus.DIRTY
    assert audits(engine) == []


def test_clean_room_reenters_availability_search(engine):
    room_id = create_room(engine)
    period = StayPeriod(date(2026, 12, 10), date(2026, 12, 13))
    with Session(engine) as s:
        assert SQLAlchemyRoomRepository(s).find_available(period, "Estándar", 2) == []
    cleaning_service(engine).finish_cleaning(room_id, uuid4(), HotelStaffRole.HOUSEKEEPING)
    with Session(engine) as s:
        found = SQLAlchemyRoomRepository(s).find_available(period, "Estándar", 2)
        assert [x.id for x in found] == [room_id]


def test_invalid_uuid_does_not_write(engine):
    with pytest.raises(ValueError, match="UUID"):
        cleaning_service(engine).finish_cleaning("not-a-uuid", uuid4(), HotelStaffRole.HOUSEKEEPING)
    assert audits(engine) == []
