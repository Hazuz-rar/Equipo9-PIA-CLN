
"""Agregado Folio: movimientos y saldos (ADR-002)."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from src.domain.folios.value_objects import (
    ChargeAmount,
    FolioId,
    PaymentAmount,
    ReservationReference,
)
from src.domain.folios.vouchers import ChargeVoucher


class FolioStatus(str, Enum):
    OPEN = "ABIERTO"
    CLOSED = "CERRADO"


@dataclass
class Charge:
    description: str
    amount: ChargeAmount
    voucher: ChargeVoucher | None = None

    def __post_init__(self) -> None:
        self.description = self.description.strip()

        if not self.description:
            raise ValueError(
                "La descripción del cargo es obligatoria."
            )

        if self.voucher is not None:
            if self.description != self.voucher.consumption_detail:
                raise ValueError(
                    "El detalle del cargo no coincide con el vale."
                )

            if self.amount.value != self.voucher.amount:
                raise ValueError(
                    "El importe del cargo no coincide con el vale."
                )


@dataclass
class Payment:
    description: str
    amount: PaymentAmount

    def __post_init__(self) -> None:
        self.description = self.description.strip()

        if not self.description:
            raise ValueError(
                "La descripción del pago es obligatoria."
            )


@dataclass
class Folio:
    id: FolioId
    reservation_id: ReservationReference
    charges: list[Charge] = field(default_factory=list)
    payments: list[Payment] = field(default_factory=list)
    status: FolioStatus = FolioStatus.OPEN

    @property
    def total_charges(self) -> Decimal:
        return sum(
            (charge.amount.value for charge in self.charges),
            Decimal("0.00"),
        )

    @property
    def total_payments(self) -> Decimal:
        return sum(
            (payment.amount.value for payment in self.payments),
            Decimal("0.00"),
        )

    @property
    def balance(self) -> Decimal:
        return self.total_charges - self.total_payments

    def add_charge(
        self,
        description: str,
        amount: ChargeAmount,
        voucher: ChargeVoucher | None = None,
    ) -> None:
        """Conserva compatibilidad con cargos históricos."""
        self._ensure_open()
        self.charges.append(
            Charge(description, amount, voucher)
        )

    def add_voucher_charge(
        self,
        voucher: ChargeVoucher,
    ) -> None:
        """Agrega un consumo respaldado por un vale RN-12."""
        self.add_charge(
            voucher.consumption_detail,
            ChargeAmount(voucher.amount),
            voucher,
        )

    def add_payment(
        self,
        description: str,
        amount: PaymentAmount,
    ) -> None:
        self._ensure_open()

        if amount.value > self.balance:
            raise ValueError(
                "El pago no puede superar el saldo pendiente."
            )

        self.payments.append(
            Payment(description, amount)
        )

    def close(self) -> None:
        self._ensure_open()

        if self.balance != Decimal("0.00"):
            raise ValueError(
                "No se puede cerrar un folio con saldo pendiente."
            )

        self.status = FolioStatus.CLOSED

    def _ensure_open(self) -> None:
        if self.status != FolioStatus.OPEN:
            raise ValueError(
                "No se puede modificar un folio cerrado."
            )
