
"""Registro preliminar de datos de check-in: RN-11, US-07 y US-08.

No guarda información en BD ni cambia el estado de la estancia.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class GuestCheckInRegistration:
    full_name: str
    official_id_number: str
    official_id_valid_until: date
    nationality: str
    contact_details: str
    invoice_requested: bool
    fiscal_address: str | None
    guarantee_accepted: bool
    registered_at: datetime

    def __post_init__(self) -> None:
        required = {
            "full_name": "Nombre completo",
            "official_id_number": "Número de identificación oficial",
            "nationality": "Nacionalidad",
            "contact_details": "Datos de contacto",
        }

        for attribute, label in required.items():
            value = getattr(self, attribute)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} es obligatorio.")

            object.__setattr__(
                self,
                attribute,
                value.strip(),
            )

        if not isinstance(self.invoice_requested, bool):
            raise ValueError(
                "La solicitud de factura debe ser booleana."
            )

        if not isinstance(self.guarantee_accepted, bool):
            raise ValueError(
                "La garantía debe indicar si fue aceptada."
            )

        address = self.fiscal_address

        if address is not None:
            if not isinstance(address, str):
                raise ValueError(
                    "El domicilio fiscal debe ser texto."
                )
            address = address.strip() or None

        object.__setattr__(
            self,
            "fiscal_address",
            address,
        )

        if self.invoice_requested and not address:
            raise ValueError(
                "El domicilio fiscal es obligatorio si solicita factura."
            )

        if not isinstance(self.registered_at, datetime):
            raise ValueError(
                "La fecha y hora del registro son obligatorias."
            )

        if (
            self.registered_at.tzinfo is None
            or self.registered_at.utcoffset() is None
        ):
            raise ValueError(
                "La fecha y hora requieren zona horaria."
            )

        if (
            not isinstance(self.official_id_valid_until, date)
            or isinstance(self.official_id_valid_until, datetime)
        ):
            raise ValueError(
                "La vigencia de identificación debe ser una fecha."
            )

        if self.official_id_valid_until < self.registered_at.date():
            raise ValueError(
                "La identificación oficial está vencida."
            )

    @property
    def missing_guarantee_risk(self) -> bool:
        """Advierte sobre la falta de garantía, conforme a US-08."""
        return not self.guarantee_accepted
