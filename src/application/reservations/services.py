
"""Casos de uso del agregado Reserva."""

from datetime import datetime
from uuid import UUID, uuid4

from src.application.ports.reservation_repository import ReservationRepository
from src.application.reservations.commands import (
    CancelReservationCommand,
    ConfirmReservationCommand,
    CreateReservationCommand,
)
from src.domain.reservations.entities import (
    Reservation,
    ReservationStatus,
)
from src.domain.reservations.policies import (
    individual_cancellation_penalty_nights,
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


class ReservationService:
    def __init__(self, repository: ReservationRepository) -> None:
        self.repository = repository
        self._availability = NoOverlappingActiveReservationsSpecification()

    def create(self, command: CreateReservationCommand) -> Reservation:
        reservation = Reservation(
            id=ReservationId(uuid4()),
            guest_id=GuestId(command.guest_id),
            room_id=RoomId(command.room_id),
            stay_period=StayPeriod(
                check_in=command.check_in,
                check_out=command.check_out,
            ),
        )
        self.repository.add(reservation)
        return reservation

    def confirm(self, command: ConfirmReservationCommand) -> Reservation:
        reservation = self._get_reservation(command.reservation_id)

        self.repository.lock_room(reservation.room_id)

        existing = self.repository.find_active_by_room_and_period(
            reservation.room_id,
            reservation.stay_period,
            reservation.id,
        )

        if not self._availability.is_satisfied_by(reservation, existing):
            raise ValueError(
                "La habitación ya tiene una reserva activa en esas fechas."
            )

        reservation.confirm()
        self.repository.update(reservation)
        return reservation

    def preview_individual_cancellation(
        self,
        reservation_id: UUID,
        arrival_at: datetime,
        requested_at: datetime,
    ) -> int:
        """Calcula las noches de penalización sin cancelar ni cobrar."""
        reservation = self._get_reservation(reservation_id)

        if reservation.status not in (
            ReservationStatus.REQUESTED,
            ReservationStatus.CONFIRMED,
        ):
            raise ValueError(
                "La reserva no admite previsualización de cancelación."
            )

        if (
            arrival_at.date() != reservation.stay_period.check_in
            or (
                arrival_at.hour,
                arrival_at.minute,
                arrival_at.second,
                arrival_at.microsecond,
            ) != (15, 0, 0, 0)
        ):
            raise ValueError(
                "La llegada debe corresponder al check-in a las 15:00."
            )

        return individual_cancellation_penalty_nights(
            arrival_at=arrival_at,
            requested_at=requested_at,
        )

    def cancel(self, command: CancelReservationCommand) -> Reservation:
        reservation = self._get_reservation(command.reservation_id)
        reservation.cancel()
        self.repository.update(reservation)
        return reservation

    def _get_reservation(self, reservation_id: UUID) -> Reservation:
        reservation = self.repository.get_by_id(
            ReservationId(reservation_id)
        )

        if reservation is None:
            raise ValueError("La reserva no existe.")

        return reservation
