from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.folios.entities import Folio, FolioStatus
from src.domain.folios.value_objects import (
    ChargeAmount,
    FolioId,
    PaymentAmount,
    ReservationReference,
)


def make_folio() -> Folio:
    return Folio(
        id=FolioId(uuid4()),
        reservation_id=ReservationReference(uuid4()),
    )


def test_folio_starts_open_with_zero_balance():
    folio = make_folio()

    assert folio.status == FolioStatus.OPEN
    assert folio.balance == Decimal("0.00")


def test_folio_can_register_charges():
    folio = make_folio()

    folio.add_charge("Hospedaje", ChargeAmount(Decimal("2500.00")))

    assert folio.total_charges == Decimal("2500.00")
    assert folio.balance == Decimal("2500.00")


def test_folio_can_register_payment():
    folio = make_folio()
    folio.add_charge("Hospedaje", ChargeAmount(Decimal("2500.00")))

    folio.add_payment("Pago con tarjeta", PaymentAmount(Decimal("1000.00")))

    assert folio.total_payments == Decimal("1000.00")
    assert folio.balance == Decimal("1500.00")


def test_payment_cannot_exceed_balance():
    folio = make_folio()
    folio.add_charge("Hospedaje", ChargeAmount(Decimal("1000.00")))

    with pytest.raises(ValueError):
        folio.add_payment("Pago", PaymentAmount(Decimal("1500.00")))


def test_folio_can_close_when_balance_is_zero():
    folio = make_folio()
    folio.add_charge("Hospedaje", ChargeAmount(Decimal("1000.00")))
    folio.add_payment("Pago", PaymentAmount(Decimal("1000.00")))

    folio.close()

    assert folio.status == FolioStatus.CLOSED


def test_folio_cannot_close_with_pending_balance():
    folio = make_folio()
    folio.add_charge("Hospedaje", ChargeAmount(Decimal("1000.00")))

    with pytest.raises(ValueError):
        folio.close()


def test_closed_folio_cannot_receive_charges():
    folio = make_folio()
    folio.add_charge("Hospedaje", ChargeAmount(Decimal("1000.00")))
    folio.add_payment("Pago", PaymentAmount(Decimal("1000.00")))
    folio.close()

    with pytest.raises(ValueError):
        folio.add_charge("Restaurante", ChargeAmount(Decimal("200.00")))


def test_charge_amount_must_be_positive():
    with pytest.raises(ValueError):
        ChargeAmount(Decimal("0"))


def test_payment_amount_must_be_positive():
    with pytest.raises(ValueError):
        PaymentAmount(Decimal("-10"))