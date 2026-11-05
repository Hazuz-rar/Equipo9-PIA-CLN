
"""Puerto de persistencia del agregado Reserva (ADR-004)."""

from typing import Protocol

from src.domain.reservations.entities import Reservation
from src.domain.reservations.value_objects import (
    ReservationId,
    RoomId,
    StayPeriod,
)


class ReservationRepository(Protocol):
    def add(self, reservation: Reservation) -> None: ...

    def get_by_id(
        self, reservation_id: ReservationId
    ) -> Reservation | None: ...

    def update(self, reservation: Reservation) -> None: ...

    def lock_room(self, room_id: RoomId) -> None:
        """Serializa confirmaciones por habitación."""
        ...

    def find_active_by_room_and_period(
        self,
        room_id: RoomId,
        stay_period: StayPeriod,
        exclude_id: ReservationId,
    ) -> list[Reservation]:
        """Busca reservas activas del mismo cuarto y fechas."""
        ...
