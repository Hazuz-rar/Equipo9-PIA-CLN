
"""Persistencia de Folio sin commit; movimientos inmutables."""

from datetime import timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.folios.entities import (
    Charge,
    Folio,
    FolioStatus,
    Payment,
)
from src.domain.folios.value_objects import (
    ChargeAmount,
    FolioId,
    PaymentAmount,
    ReservationReference,
)
from src.domain.folios.vouchers import ChargeVoucher
from src.infrastructure.database.models.folio_model import (
    FolioChargeModel,
    FolioModel,
    FolioPaymentModel,
)


class SQLAlchemyFolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, folio: Folio) -> None:
        self._validate_folio(folio)

        self.session.add(
            FolioModel(
                id=folio.id.value,
                reservation_id=folio.reservation_id.value,
                status=folio.status,
            )
        )

        self.session.flush()

        self._append_movements(folio.id, folio, 0, 0)
        self.session.flush()

    def get_by_id(
        self,
        folio_id: FolioId,
    ) -> Folio | None:
        model = self.session.get(
            FolioModel,
            folio_id.value,
        )

        if model is None:
            return None

        folio = Folio(
            id=FolioId(model.id),
            reservation_id=ReservationReference(
                model.reservation_id
            ),
            status=model.status,
        )

        for row in self._get_charges(folio_id):
            folio.charges.append(
                Charge(
                    row.description,
                    ChargeAmount(row.amount),
                    self._to_voucher(row),
                )
            )

        for row in self._get_payments(folio_id):
            folio.payments.append(
                Payment(
                    row.description,
                    PaymentAmount(row.amount),
                )
            )

        return folio

    def update(self, folio: Folio) -> None:
        self._validate_folio(folio)

        model = self.session.scalar(
            select(FolioModel)
            .where(FolioModel.id == folio.id.value)
            .with_for_update()
        )

        if model is None:
            raise ValueError(
                "El folio no existe en la base de datos."
            )

        if model.reservation_id != folio.reservation_id.value:
            raise ValueError(
                "No puede cambiarse la reserva del folio."
            )

        charges = self._get_charges(folio.id)
        payments = self._get_payments(folio.id)

        if (
            len(folio.charges) < len(charges)
            or len(folio.payments) < len(payments)
        ):
            raise ValueError(
                "No pueden eliminarse movimientos registrados."
            )

        if any(
            charge.description != row.description
            or charge.amount.value != row.amount
            or charge.voucher != self._to_voucher(row)
            for charge, row in zip(folio.charges, charges)
        ) or any(
            payment.description != row.description
            or payment.amount.value != row.amount
            for payment, row in zip(folio.payments, payments)
        ):
            raise ValueError(
                "No pueden modificarse movimientos registrados."
            )

        if model.status == FolioStatus.CLOSED:
            if (
                len(folio.charges) != len(charges)
                or len(folio.payments) != len(payments)
                or folio.status != FolioStatus.CLOSED
            ):
                raise ValueError(
                    "No se puede modificar un folio cerrado."
                )

        if model.status == FolioStatus.OPEN and folio.status not in (
            FolioStatus.OPEN,
            FolioStatus.CLOSED,
        ):
            raise ValueError(
                "Estado de folio inválido."
            )

        self._append_movements(
            folio.id,
            folio,
            len(charges),
            len(payments),
        )

        model.status = folio.status
        self.session.flush()

    @staticmethod
    def _validate_folio(folio: Folio) -> None:
        if (
            folio.status == FolioStatus.CLOSED
            and folio.balance != Decimal("0")
        ):
            raise ValueError(
                "No se puede cerrar un folio con saldo pendiente."
            )

    def _get_charges(
        self,
        folio_id: FolioId,
    ) -> list[FolioChargeModel]:
        return list(
            self.session.scalars(
                select(FolioChargeModel)
                .where(
                    FolioChargeModel.folio_id
                    == folio_id.value
                )
                .order_by(FolioChargeModel.id)
            )
        )

    def _get_payments(
        self,
        folio_id: FolioId,
    ) -> list[FolioPaymentModel]:
        return list(
            self.session.scalars(
                select(FolioPaymentModel)
                .where(
                    FolioPaymentModel.folio_id
                    == folio_id.value
                )
                .order_by(FolioPaymentModel.id)
            )
        )

    @staticmethod
    def _to_voucher(
        row: FolioChargeModel,
    ) -> ChargeVoucher | None:
        if row.voucher_number is None:
            return None

        issued_at = row.voucher_issued_at

        if issued_at is None:
            raise ValueError(
                "El cargo tiene un vale incompleto."
            )

        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(
                tzinfo=timezone.utc
            )

        return ChargeVoucher(
            room_number=row.voucher_room_number,
            guest_name=row.voucher_guest_name,
            guest_signature=row.voucher_guest_signature,
            issued_at=issued_at,
            point_of_sale=row.voucher_point_of_sale,
            consumption_detail=row.voucher_consumption_detail,
            amount=row.amount,
            voucher_number=row.voucher_number,
        )

    def _append_movements(
        self,
        folio_id: FolioId,
        folio: Folio,
        charge_start: int,
        payment_start: int,
    ) -> None:
        for charge in folio.charges[charge_start:]:
            voucher = charge.voucher

            self.session.add(
                FolioChargeModel(
                    folio_id=folio_id.value,
                    description=charge.description,
                    amount=charge.amount.value,
                    voucher_room_number=(
                        voucher.room_number if voucher else None
                    ),
                    voucher_guest_name=(
                        voucher.guest_name if voucher else None
                    ),
                    voucher_guest_signature=(
                        voucher.guest_signature if voucher else None
                    ),
                    voucher_issued_at=(
                        voucher.issued_at.astimezone(timezone.utc)
                        if voucher else None
                    ),
                    voucher_point_of_sale=(
                        voucher.point_of_sale if voucher else None
                    ),
                    voucher_consumption_detail=(
                        voucher.consumption_detail
                        if voucher else None
                    ),
                    voucher_number=(
                        voucher.voucher_number if voucher else None
                    ),
                )
            )

        for payment in folio.payments[payment_start:]:
            self.session.add(
                FolioPaymentModel(
                    folio_id=folio_id.value,
                    description=payment.description,
                    amount=payment.amount.value,
                )
            )
