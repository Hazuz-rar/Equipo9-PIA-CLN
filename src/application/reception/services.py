
"""Registro documental previo al check-in: RN-11, US-07 y US-08.

No ejecuta check-in ni abre folios. El almacenamiento
cifrado se representa mediante un puerto.
"""

from typing import Protocol
from uuid import UUID

from src.domain.reception.check_in import (
    GuestCheckInRegistration,
)
from src.domain.reservations.entities import ReservationStatus
from src.domain.reservations.value_objects import ReservationId
from src.application.ports.reservation_repository import (
    ReservationRepository,
)


class CheckInRecordStore(Protocol):
    def add(
        self,
        reservation_id: UUID,
        record: GuestCheckInRegistration,
    ) -> None: ...

    def get_by_reservation_id(
        self,
        reservation_id: UUID,
    ) -> GuestCheckInRegistration | None: ...


class CheckInRegistrationService:
    def __init__(
        self,
        reservations: ReservationRepository,
        records: CheckInRecordStore,
    ):
        self.reservations = reservations
        self.records = records

    def register(
        self,
        reservation_id: UUID,
        record: GuestCheckInRegistration,
    ) -> bool:
        """Guarda datos validados; devuelve True si falta garantía.

        El dueño de la sesión realiza COMMIT o ROLLBACK.
        """
        reservation = self.reservations.get_by_id(
            ReservationId(reservation_id)
        )

        if reservation is None:
            raise ValueError("La reserva no existe.")

        if reservation.status != ReservationStatus.CONFIRMED:
            raise ValueError(
                "Solo puede registrarse documentación "
                "de una reserva confirmada."
            )

        if self.records.get_by_reservation_id(
            reservation_id
        ) is not None:
            raise ValueError(
                "La documentación del check-in ya fue registrada."
            )

        self.records.add(reservation_id, record)
        return record.missing_guarantee_risk
