from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class RoomNumber:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()

        if not normalized:
            raise ValueError("El número de habitación es obligatorio.")

        if len(normalized) > 10:
            raise ValueError(
                "El número de habitación no puede superar 10 caracteres."
            )

        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class Capacity:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or self.value < 1:
            raise ValueError(
                "La capacidad debe ser un entero mayor que cero."
            )


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "MXN"

    def __post_init__(self) -> None:
        if not self.amount.is_finite():
            raise ValueError("El importe debe ser un número válido.")

        if self.amount < Decimal("0"):
            raise ValueError("El importe no puede ser negativo.")

        if self.currency != "MXN":
            raise ValueError(
                "En esta versión el sistema maneja importes en MXN."
            )
        