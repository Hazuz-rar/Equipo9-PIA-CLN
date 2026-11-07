from datetime import date
from uuid import UUID, uuid4

import pytest

from src.application.reservations.commands import (
    CancelReservationCommand,
    ConfirmReservationCommand,
    CreateReservationCommand,
)
from src.application.reservations.services import ReservationService
from src.domain.reservations.entities import ReservationStatus


from decimal import Decimal

from src.domain.rooms.entities import Room, RoomStatus
from src.domain.rooms.value_objects import (
    RoomNumber,
    Capacity,
    Money,
)


class InMemoryReservationRepository:

    def __init__(self):
        self.reservations = {}

    def add(self, reservation):
        self.reservations[reservation.id.value] = reservation

    def get_by_id(self, reservation_id):
        return self.reservations.get(reservation_id.value)

    def update(self, reservation):
        self.reservations[reservation.id.value] = reservation

    
    def lock_room(self, room_id):
        pass

    def find_active_by_room_and_period(
        self, room_id, stay_period, exclude_id
    ):
        return [
            r
            for r in self.reservations.values()
            if r.room_id == room_id
            and r.id != exclude_id
            and r.status in (
                ReservationStatus.CONFIRMED,
                ReservationStatus.CHECK_IN,
            )
            and r.stay_period.check_in < stay_period.check_out
            and r.stay_period.check_out > stay_period.check_in
        ]


class InMemoryRoomRepository:
    def __init__(self):
        self.rooms = {}

    def get_by_id(self, room_id):
        return self.rooms.get(room_id.value)


def sample_room(status=RoomStatus.AVAILABLE):
    return Room(
        number=RoomNumber("D-101"),
        room_type="Estándar",
        capacity=Capacity(2),
        base_rate=Money(Decimal("1250.00")),
        status=status,
    )


@pytest.fixture
def service():
    return ReservationService(
        InMemoryReservationRepository(),
        InMemoryRoomRepository(),
    )



def test_service_creates_reservation(service):
    command = CreateReservationCommand(
        guest_id=uuid4(),
        room_id=uuid4(),
        check_in=date(2026, 11, 10),
        check_out=date(2026, 11, 13),
    )

    reservation = service.create(command)

    assert reservation.status == ReservationStatus.REQUESTED
    assert reservation.guest_id.value == command.guest_id
    assert reservation.room_id.value == command.room_id


def test_service_confirms_reservation(service):
    reservation = service.create(
        CreateReservationCommand(
            guest_id=uuid4(),
            room_id=uuid4(),
            check_in=date(2026, 11, 10),
            check_out=date(2026, 11, 13),
        )
    )

    service.room_repository.rooms[
        reservation.room_id.value
    ] = sample_room()

    service.confirm(
        ConfirmReservationCommand(
            reservation_id=reservation.id.value
        )
    )

    assert reservation.status == ReservationStatus.CONFIRMED


def test_service_cancels_reservation(service):
    reservation = service.create(
        CreateReservationCommand(
            guest_id=uuid4(),
            room_id=uuid4(),
            check_in=date(2026, 11, 10),
            check_out=date(2026, 11, 13),
        )
    )

    service.cancel(
        CancelReservationCommand(
            reservation_id=reservation.id.value
        )
    )

    assert reservation.status == ReservationStatus.CANCELLED


def test_service_rejects_nonexistent_reservation(service):
    with pytest.raises(ValueError, match="La reserva no existe"):
        service.confirm(
            ConfirmReservationCommand(
                reservation_id=uuid4()
            )
        )


def test_service_rejects_missing_room(service):
    reservation = service.create(
        CreateReservationCommand(
            guest_id=uuid4(),
            room_id=uuid4(),
            check_in=date(2026, 12, 10),
            check_out=date(2026, 12, 13),
        )
    )

    with pytest.raises(
        ValueError,
        match="no existe en el inventario",
    ):
        service.confirm(
            ConfirmReservationCommand(
                reservation.id.value
            )
        )

    assert reservation.status == ReservationStatus.REQUESTED


@pytest.mark.parametrize(
    "status",
    [
        RoomStatus.OUT_OF_ORDER,
        RoomStatus.OCCUPIED,
    ],
)
def test_service_rejects_room_not_available(
    service,
    status,
):
    reservation = service.create(
        CreateReservationCommand(
            guest_id=uuid4(),
            room_id=uuid4(),
            check_in=date(2026, 12, 10),
            check_out=date(2026, 12, 13),
        )
    )

    service.room_repository.rooms[
        reservation.room_id.value
    ] = sample_room(status)

    with pytest.raises(
        ValueError,
        match="no está habilitada",
    ):
        service.confirm(
            ConfirmReservationCommand(
                reservation.id.value
            )
        )

    assert reservation.status == ReservationStatus.REQUESTED
