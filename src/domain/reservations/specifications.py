
"""Specification para detectar reservas activas con estancia superpuesta.

Trazabilidad: US-04, US-25 y ADR-002. Este objeto evalúa la regla
sobre reservas recibidas; la consulta de BD y el bloqueo transaccional
para evitar carreras entre solicitudes aún deben implementarse.
"""

from collections.abc import Iterable

from src.domain.reservations.entities import Reservation, ReservationStatus


class NoOverlappingActiveReservationsSpecification:
    """Comprueba que una misma habitación no tenga periodos activos cruzados."""

    _BLOCKING_STATUSES = frozenset(
        {ReservationStatus.CONFIRMED, ReservationStatus.CHECK_IN}
    )

    def is_satisfied_by(
        self,
        candidate: Reservation,
        existing_reservations: Iterable[Reservation],
    ) -> bool:
        for other in existing_reservations:
            if other.id == candidate.id or other.room_id != candidate.room_id:
                continue
            if other.status not in self._BLOCKING_STATUSES:
                continue
            if (
                candidate.stay_period.check_in < other.stay_period.check_out
                and other.stay_period.check_in < candidate.stay_period.check_out
            ):
                return False
        return True
