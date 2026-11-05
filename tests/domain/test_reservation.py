from datetime import date
from uuid import uuid4

import pytest

from src.domain.reservations.entities import (
    Reservation,
    ReservationStatus,
)
from src.domain.reservations.value_objects import (
    GuestId,
    ReservationId,
    RoomId,
    StayPeriod,
)


def make_reservation() -> Reservation:
    return Reservation(
        id=ReservationId(uuid4()),
        guest_id=GuestId(uuid4()),
        room_id=RoomId(uuid4()),
        stay_period=StayPeriod(
            check_in=date(2026, 11, 10),
            check_out=date(2026, 11, 13),
        ),
    )


def test_reservation_is_created_as_requested():
    reservation = make_reservation()

    assert reservation.status == ReservationStatus.REQUESTED
    assert reservation.stay_period.nights == 3


def test_reservation_can_be_confirmed():
    reservation = make_reservation()

    reservation.confirm()

    assert reservation.status == ReservationStatus.CONFIRMED


def test_reservation_can_complete_lifecycle():
    reservation = make_reservation()

    reservation.confirm()
    reservation.check_in()
    reservation.check_out()

    assert reservation.status == ReservationStatus.CHECK_OUT


def test_requested_reservation_can_be_cancelled():
    reservation = make_reservation()

    reservation.cancel()

    assert reservation.status == ReservationStatus.CANCELLED


def test_cannot_check_in_without_confirmation():
    reservation = make_reservation()

    with pytest.raises(ValueError):
        reservation.check_in()


def test_cannot_confirm_cancelled_reservation():
    reservation = make_reservation()
    reservation.cancel()

    with pytest.raises(ValueError):
        reservation.confirm()


def test_checkout_must_be_after_checkin():
    with pytest.raises(ValueError):
        StayPeriod(
            check_in=date(2026, 11, 13),
            check_out=date(2026, 11, 10),
        )
        