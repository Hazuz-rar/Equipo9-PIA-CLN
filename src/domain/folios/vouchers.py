
"""Datos obligatorios del vale: RN-12, RF-05 y US-10.

Este Value Object valida el comprobante, pero todavía
no lo almacena en PostgreSQL.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ChargeVoucher:
    room_number: str
    guest_name: str
    guest_signature: str
    issued_at: datetime
    point_of_sale: str
    consumption_detail: str
    amount: Decimal
    voucher_number: str

    def __post_init__(self) -> None:
        fields = (
            ("Número de habitación", "room_number"),
            ("Nombre del huésped", "guest_name"),
            ("Firma del huésped", "guest_signature"),
            ("Punto de venta", "point_of_sale"),
            ("Detalle del consumo", "consumption_detail"),
            ("Folio del vale", "voucher_number"),
        )

        for label, field_name in fields:
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} es obligatorio.")

            object.__setattr__(
                self,
                field_name,
                value.strip(),
            )

        if not isinstance(self.issued_at, datetime):
            raise ValueError(
                "La fecha y hora del vale son obligatorias."
            )

        if (
            self.issued_at.tzinfo is None
            or self.issued_at.utcoffset() is None
        ):
            raise ValueError(
                "La fecha y hora del vale requieren zona horaria."
            )

        if (
            not isinstance(self.amount, Decimal)
            or not self.amount.is_finite()
        ):
            raise ValueError(
                "El importe del vale debe ser un Decimal válido."
            )

        if self.amount <= Decimal("0"):
            raise ValueError(
                "El importe del vale debe ser mayor que cero."
            )
