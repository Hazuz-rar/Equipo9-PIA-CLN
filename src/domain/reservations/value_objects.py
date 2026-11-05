from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class ReservationId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("El ID de reserva debe ser un UUID.")


@dataclass(frozen=True)
class GuestId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("El ID del huésped debe ser un UUID.")


@dataclass(frozen=True)
class RoomId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("El ID de habitación debe ser un UUID.")


@dataclass(frozen=True)
class StayPeriod:
    check_in: date
    check_out: date

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise ValueError(
                "La fecha de salida debe ser posterior a la fecha de entrada."
            )

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days
    