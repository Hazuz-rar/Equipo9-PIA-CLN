
"""Pruebas de vales RN-12 y US-10."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.domain.folios.vouchers import ChargeVoucher


def valid_voucher(**changes):
    data = {
        "room_number": "120",
        "guest_name": "Huésped de prueba",
        "guest_signature": "firma-de-prueba",
        "issued_at": datetime(
            2026, 12, 10, 18, 0,
            tzinfo=timezone.utc,
        ),
        "point_of_sale": "Restaurante",
        "consumption_detail": "Consumo de prueba",
        "amount": Decimal("350.00"),
        "voucher_number": "V-123",
    }

    data.update(changes)
    return ChargeVoucher(**data)


def test_valid_voucher_has_all_required_fields():
    voucher = valid_voucher()

    assert voucher.room_number == "120"
    assert voucher.amount == Decimal("350.00")


@pytest.mark.parametrize(
    ("field", "error"),
    [
        ("room_number", "Número de habitación"),
        ("guest_name", "Nombre del huésped"),
        ("guest_signature", "Firma del huésped"),
        ("point_of_sale", "Punto de venta"),
        ("consumption_detail", "Detalle del consumo"),
        ("voucher_number", "Folio del vale"),
    ],
)
def test_rejects_missing_text_field(field, error):
    with pytest.raises(ValueError, match=error):
        valid_voucher(**{field: "  "})


def test_rejects_missing_issued_at():
    with pytest.raises(ValueError, match="fecha y hora"):
        valid_voucher(issued_at=None)


def test_rejects_naive_datetime():
    with pytest.raises(ValueError, match="zona horaria"):
        valid_voucher(
            issued_at=datetime(2026, 12, 10, 18, 0)
        )


@pytest.mark.parametrize(
    "amount",
    [Decimal("0"), Decimal("-1")],
)
def test_rejects_nonpositive_amount(amount):
    with pytest.raises(
        ValueError,
        match="mayor que cero",
    ):
        valid_voucher(amount=amount)


def test_rejects_invalid_decimal():
    with pytest.raises(
        ValueError,
        match="Decimal válido",
    ):
        valid_voucher(amount=Decimal("NaN"))


def test_strips_extra_spaces():
    voucher = valid_voucher(
        guest_name="  Huésped de prueba  "
    )

    assert voucher.guest_name == "Huésped de prueba"
