"""Agregado Reserva y transiciones explícitas de su ciclo de vida.

Esta máquina de estados representa solo las transiciones ya implementadas.
RN-04/US-05 requieren ampliar la cancelación para reservas confirmadas
junto con el cálculo de penalizaciones y reembolsos; esa parte está pendiente.
"""

from dataclasses import dataclass
from enum import Enum

from src.domain.reservations.value_objects import (
    GuestId,
    ReservationId,
    RoomId,
    StayPeriod,
)


class ReservationStatus(str, Enum):
    REQUESTED = "SOLICITADA"
    CONFIRMED = "CONFIRMADA"
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"
    CANCELLED = "CANCELADA"
    NO_SHOW = "NO_SHOW"
    RELOCATED = "REUBICADA"


class ReservationAction(str, Enum):
    CONFIRM = "CONFIRMAR"
    CHECK_IN = "REGISTRAR_CHECK_IN"
    CHECK_OUT = "REGISTRAR_CHECK_OUT"
    CANCEL = "CANCELAR"
    POLICY_CANCEL = "CANCELAR_CON_POLITICA"
    MARK_NO_SHOW = "MARCAR_NO_SHOW"
    RELOCATE = "REUBICAR"


class ReservationStateMachine:
    """Define centralmente las transiciones válidas del agregado Reserva."""

    _TRANSITIONS = {
        (ReservationStatus.REQUESTED, ReservationAction.CONFIRM): ReservationStatus.CONFIRMED,
        (ReservationStatus.REQUESTED, ReservationAction.CANCEL): ReservationStatus.CANCELLED,
        (ReservationStatus.CONFIRMED, ReservationAction.POLICY_CANCEL): ReservationStatus.CANCELLED,
        (ReservationStatus.CONFIRMED, ReservationAction.MARK_NO_SHOW): ReservationStatus.NO_SHOW,
        (ReservationStatus.CONFIRMED, ReservationAction.RELOCATE): ReservationStatus.RELOCATED,
        (ReservationStatus.CONFIRMED, ReservationAction.CHECK_IN): ReservationStatus.CHECK_IN,
        (ReservationStatus.CHECK_IN, ReservationAction.CHECK_OUT): ReservationStatus.CHECK_OUT,
    }

    @classmethod
    def next_status(
        cls, current: ReservationStatus, action: ReservationAction
    ) -> ReservationStatus:
        try:
            return cls._TRANSITIONS[(current, action)]
        except KeyError:
            raise ValueError("Transición de reserva no permitida.") from None


@dataclass
class Reservation:
    id: ReservationId
    guest_id: GuestId
    room_id: RoomId
    stay_period: StayPeriod
    status: ReservationStatus = ReservationStatus.REQUESTED

    def _apply(self, action: ReservationAction, error_message: str) -> None:
        try:
            next_status = ReservationStateMachine.next_status(self.status, action)
        except ValueError:
            raise ValueError(error_message) from None
        self.status = next_status

    def confirm(self) -> None:
        self._apply(
            ReservationAction.CONFIRM,
            "Solo una reserva solicitada puede confirmarse.",
        )

    def check_in(self) -> None:
        self._apply(
            ReservationAction.CHECK_IN,
            "Solo una reserva confirmada puede iniciar el check-in.",
        )

    def check_out(self) -> None:
        self._apply(
            ReservationAction.CHECK_OUT,
            "Solo una reserva con check-in puede finalizar.",
        )

    def cancel(self) -> None:
        self._apply(
            ReservationAction.CANCEL,
            "Solo una reserva solicitada puede cancelarse.",
        )

    def cancel_with_policy(self) -> None:
        """RN-04: el servicio debe calcular y registrar importe antes de invocar."""
        self._apply(ReservationAction.POLICY_CANCEL,
                    'Solo una reserva confirmada permite cancelación con política.')

    def mark_no_show(self) -> None:
        """RN-05: el caso de uso verifica plazo y garantía antes de invocar."""
        self._apply(ReservationAction.MARK_NO_SHOW,
                    'Solo una reserva confirmada puede ser No-Show.')

    def relocate(self) -> None:
        """RN-06: solo con evidencia de hotel aliado registrada por el caso de uso."""
        self._apply(ReservationAction.RELOCATE,
                    'Solo una reserva confirmada puede reubicarse.')
