
"""Pruebas del State Machine y del patrón Specification de reservas."""

from datetime import date
from uuid import uuid4

import pytest

from src.domain.reservations.entities import (
    Reservation,
    ReservationAction,
    ReservationStateMachine,
    ReservationStatus,
)
from src.domain.reservations.specifications import (
    NoOverlappingActiveReservationsSpecification,
)
from src.domain.reservations.value_objects import (
    GuestId,
    ReservationId,
    RoomId,
    StayPeriod,
)


def make_reservation(
    room_id=None,
    check_in=date(2026, 12, 10),
    check_out=date(2026, 12, 13),
    status=ReservationStatus.REQUESTED,
):
    return Reservation(
        id=ReservationId(uuid4()),
        guest_id=GuestId(uuid4()),
        room_id=RoomId(room_id or uuid4()),
        stay_period=StayPeriod(check_in=check_in, check_out=check_out),
        status=status,
    )


def test_state_machine_allows_requested_confirmation():
    assert ReservationStateMachine.next_status(
        ReservationStatus.REQUESTED, ReservationAction.CONFIRM
    ) == ReservationStatus.CONFIRMED


def test_state_machine_rejects_invalid_transition():
    with pytest.raises(ValueError, match="Transición de reserva no permitida"):
        ReservationStateMachine.next_status(
            ReservationStatus.CANCELLED, ReservationAction.CONFIRM
        )


def test_confirmed_reservation_cannot_be_confirmed_twice():
    reservation = make_reservation()
    reservation.confirm()
    with pytest.raises(ValueError, match="Solo una reserva solicitada"):
        reservation.confirm()
    assert reservation.status == ReservationStatus.CONFIRMED


def test_invalid_checkout_keeps_previous_status():
    reservation = make_reservation()
    with pytest.raises(ValueError, match="Solo una reserva con check-in"):
        reservation.check_out()
    assert reservation.status == ReservationStatus.REQUESTED


def test_specification_rejects_overlap_with_confirmed_reservation():
    room_id = uuid4()
    existing = make_reservation(room_id=room_id, status=ReservationStatus.CONFIRMED)
    candidate = make_reservation(
        room_id=room_id, check_in=date(2026, 12, 11), check_out=date(2026, 12, 14)
    )
    assert not NoOverlappingActiveReservationsSpecification().is_satisfied_by(
        candidate, [existing]
    )


def test_specification_rejects_overlap_with_checked_in_reservation():
    room_id = uuid4()
    existing = make_reservation(room_id=room_id, status=ReservationStatus.CHECK_IN)
    candidate = make_reservation(room_id=room_id)
    assert not NoOverlappingActiveReservationsSpecification().is_satisfied_by(
        candidate, [existing]
    )


def test_specification_allows_adjoining_stays():
    room_id = uuid4()
    existing = make_reservation(room_id=room_id, status=ReservationStatus.CONFIRMED)
    candidate = make_reservation(
        room_id=room_id, check_in=date(2026, 12, 13), check_out=date(2026, 12, 15)
    )
    assert NoOverlappingActiveReservationsSpecification().is_satisfied_by(
        candidate, [existing]
    )


def test_specification_allows_different_room():
    existing = make_reservation(status=ReservationStatus.CONFIRMED)
    candidate = make_reservation()
    assert NoOverlappingActiveReservationsSpecification().is_satisfied_by(
        candidate, [existing]
    )


def test_specification_ignores_requested_or_cancelled_reservations():
    room_id = uuid4()
    requested = make_reservation(room_id=room_id, status=ReservationStatus.REQUESTED)
    cancelled = make_reservation(room_id=room_id, status=ReservationStatus.CANCELLED)
    candidate = make_reservation(room_id=room_id)
    assert NoOverlappingActiveReservationsSpecification().is_satisfied_by(
        candidate, [requested, cancelled]
    )


def test_specification_does_not_conflict_with_self():
    candidate = make_reservation(status=ReservationStatus.CONFIRMED)
    assert NoOverlappingActiveReservationsSpecification().is_satisfied_by(
        candidate, [candidate]
    )
