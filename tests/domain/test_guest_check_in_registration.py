
"""Pruebas RN-11, US-07 y US-08."""

from datetime import date, datetime, timedelta, timezone

import pytest

from src.domain.reception.check_in import (
    GuestCheckInRegistration,
)


REGISTERED_AT = datetime(
    2026, 12, 10, 15,
    tzinfo=timezone(timedelta(hours=-6)),
)


def valid_registration(**changes):
    data = {
        "full_name": "Huésped de prueba",
        "official_id_number": "ID-PRUEBA-123",
        "official_id_valid_until": date(2027, 1, 1),
        "nationality": "Mexicana",
        "contact_details": "contacto de prueba",
        "invoice_requested": False,
        "fiscal_address": None,
        "guarantee_accepted": True,
        "registered_at": REGISTERED_AT,
    }

    data.update(changes)
    return GuestCheckInRegistration(**data)


def test_accepts_complete_registration():
    record = valid_registration()

    assert record.full_name == "Huésped de prueba"
    assert record.missing_guarantee_risk is False


@pytest.mark.parametrize(
    "field",
    [
        "full_name",
        "official_id_number",
        "nationality",
        "contact_details",
    ],
)
def test_rejects_missing_required_text(field):
    with pytest.raises(ValueError, match="obligatorio"):
        valid_registration(**{field: "   "})


def test_requires_fiscal_address_for_invoice():
    with pytest.raises(ValueError, match="domicilio fiscal"):
        valid_registration(invoice_requested=True)


def test_accepts_valid_fiscal_address():
    record = valid_registration(
        invoice_requested=True,
        fiscal_address="  Domicilio fiscal de prueba ",
    )

    assert record.fiscal_address == "Domicilio fiscal de prueba"


def test_rejects_expired_identification():
    with pytest.raises(ValueError, match="vencida"):
        valid_registration(
            official_id_valid_until=date(2026, 12, 9)
        )


def test_accepts_identification_expiring_today():
    record = valid_registration(
        official_id_valid_until=date(2026, 12, 10)
    )

    assert record.official_id_valid_until == date(
        2026, 12, 10
    )


def test_warns_when_guarantee_missing():
    record = valid_registration(
        guarantee_accepted=False
    )

    assert record.missing_guarantee_risk is True


def test_rejects_datetime_without_timezone():
    with pytest.raises(ValueError, match="zona horaria"):
        valid_registration(
            registered_at=datetime(2026, 12, 10, 15)
        )


def test_rejects_invalid_bool_flags():
    with pytest.raises(ValueError, match="booleana"):
        valid_registration(invoice_requested="no")

    with pytest.raises(ValueError, match="garantía"):
        valid_registration(guarantee_accepted=None)


def test_rejects_nondatetime_registered_at():
    with pytest.raises(ValueError, match="fecha y hora"):
        valid_registration(
            registered_at=date(2026, 12, 10)
        )
