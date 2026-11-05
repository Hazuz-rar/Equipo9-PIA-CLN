from decimal import Decimal

import pytest

from src.domain.rooms.entities import Room, RoomStatus
from src.domain.rooms.value_objects import (
    Capacity,
    Money,
    RoomNumber,
)


def make_room() -> Room:
    return Room(
        number=RoomNumber(" 101 "),
        room_type="Estándar",
        capacity=Capacity(2),
        base_rate=Money(Decimal("1200.00")),
    )


def test_room_is_created_available_and_normalizes_number():
    room = make_room()

    assert room.number.value == "101"
    assert room.status == RoomStatus.AVAILABLE


def test_room_can_be_occupied_and_released():
    room = make_room()

    room.mark_occupied()
    assert room.status == RoomStatus.OCCUPIED

    room.mark_available()
    assert room.status == RoomStatus.AVAILABLE


def test_unavailable_room_cannot_be_occupied():
    room = make_room()
    room.mark_out_of_order()

    with pytest.raises(ValueError):
        room.mark_occupied()


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        Capacity(0)


def test_money_cannot_be_negative():
    with pytest.raises(ValueError):
        Money(Decimal("-1.00"))


def test_room_requires_type():
    with pytest.raises(ValueError):
        Room(
            number=RoomNumber("102"),
            room_type=" ",
            capacity=Capacity(2),
            base_rate=Money(Decimal("1000.00")),
        )