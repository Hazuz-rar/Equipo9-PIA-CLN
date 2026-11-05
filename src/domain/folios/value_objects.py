from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class FolioId:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("El ID del folio debe ser un UUID.")


@dataclass(frozen=True)
class ReservationReference:
    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise ValueError("La referencia de reserva debe ser un UUID.")


@dataclass(frozen=True)
class ChargeAmount:
    value: Decimal

    def __post_init__(self) -> None:
        if not self.value.is_finite():
            raise ValueError("El importe debe ser válido.")
        if self.value <= Decimal("0"):
            raise ValueError("El importe debe ser mayor que cero.")


@dataclass(frozen=True)
class PaymentAmount:
    value: Decimal

    def __post_init__(self) -> None:
        if not self.value.is_finite():
            raise ValueError("El importe del pago debe ser válido.")
        if self.value <= Decimal("0"):
            raise ValueError("El pago debe ser mayor que cero.")