
"""Esquemas de lectura de folios para API REST."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from src.domain.folios.entities import Folio


class FolioMovementResponse(BaseModel):
    description: str
    amount: Decimal


class FolioResponse(BaseModel):
    id: UUID
    reservation_id: UUID
    status: str

    charges: list[FolioMovementResponse]
    payments: list[FolioMovementResponse]

    total_charges: Decimal
    total_payments: Decimal
    balance: Decimal

    @classmethod
    def from_domain(
        cls,
        folio: Folio,
    ) -> "FolioResponse":
        return cls(
            id=folio.id.value,
            reservation_id=folio.reservation_id.value,
            status=folio.status.value,
            charges=[
                FolioMovementResponse(
                    description=c.description,
                    amount=c.amount.value,
                )
                for c in folio.charges
            ],
            payments=[
                FolioMovementResponse(
                    description=p.description,
                    amount=p.amount.value,
                )
                for p in folio.payments
            ],
            total_charges=folio.total_charges,
            total_payments=folio.total_payments,
            balance=folio.balance,
        )
