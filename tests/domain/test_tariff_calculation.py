
"""Pruebas de tarifas: RN-13, US-03 y ADR-003.

Todos los precios y factores utilizados son ilustrativos.
"""

from datetime import date
from decimal import Decimal

import pytest

from src.domain.reservations.pricing import (
    TariffCalculationService,
    TariffRules,
)
from src.domain.reservations.value_objects import StayPeriod


def configured_rules():
    return TariffRules(
        bar_by_room_and_season={
            ("estandar", "alta"): Decimal("1500.00"),
            ("estandar", "baja"): Decimal("1000.00"),
        },
        weekend_multiplier=Decimal("1.20"),
        channel_multipliers={
            "directo": Decimal("1.00"),
            "ota": Decimal("1.10"),
        },
        customer_multipliers={
            "directo": Decimal("1.00"),
            "ota": Decimal("1.00"),
        },
        currency="MXN",
    )


def quote(check_in, check_out, seasons, **kwargs):
    return TariffCalculationService().quote(
        stay_period=StayPeriod(check_in, check_out),
        room_type="estandar",
        channel=kwargs.pop("channel", "directo"),
        customer_type=kwargs.pop("customer_type", "directo"),
        season_by_date=seasons,
        rules=kwargs.pop("rules", configured_rules()),
        **kwargs,
    )


def test_friday_and_saturday_use_configured_increase():
    result = quote(
        date(2026, 12, 11),
        date(2026, 12, 13),
        {
            date(2026, 12, 11): "alta",
            date(2026, 12, 12): "alta",
        },
    )

    assert [night.amount for night in result.nights] == [
        Decimal("1800.00"),
        Decimal("1800.00"),
    ]

    assert result.total == Decimal("3600.00")
    assert result.currency == "MXN"


def test_season_is_applied_to_each_night():
    result = quote(
        date(2026, 12, 13),
        date(2026, 12, 15),
        {
            date(2026, 12, 13): "alta",
            date(2026, 12, 14): "baja",
        },
    )

    assert result.total == Decimal("2500.00")


def test_ota_channel_modifies_bar():
    result = quote(
        date(2026, 12, 13),
        date(2026, 12, 14),
        {
            date(2026, 12, 13): "baja",
        },
        channel="ota",
        customer_type="ota",
    )

    assert result.total == Decimal("1100.00")


def test_active_corporate_contract_replaces_bar():
    result = quote(
        date(2026, 12, 11),
        date(2026, 12, 13),
        {
            date(2026, 12, 11): "alta",
            date(2026, 12, 12): "alta",
        },
        customer_type="corporativo",
        contracted_nightly_rate=Decimal("950.00"),
        contract_valid=True,
    )

    assert result.total == Decimal("1900.00")


def test_negotiated_rate_requires_valid_contract():
    with pytest.raises(ValueError, match="contrato vigente"):
        quote(
            date(2026, 12, 13),
            date(2026, 12, 14),
            {
                date(2026, 12, 13): "alta",
            },
            customer_type="negociado",
            contracted_nightly_rate=Decimal("900.00"),
        )


def test_missing_season_is_rejected():
    with pytest.raises(ValueError, match="Falta temporada"):
        quote(
            date(2026, 12, 13),
            date(2026, 12, 14),
            {},
        )


def test_missing_bar_is_rejected():
    rules = TariffRules(
        bar_by_room_and_season={
            ("suite", "alta"): Decimal("2000"),
        },
        weekend_multiplier=Decimal("1.2"),
        channel_multipliers={
            "directo": Decimal("1"),
        },
        customer_multipliers={
            "directo": Decimal("1"),
        },
        currency="MXN",
    )

    with pytest.raises(ValueError, match="No hay tarifa BAR"):
        quote(
            date(2026, 12, 13),
            date(2026, 12, 14),
            {
                date(2026, 12, 13): "alta",
            },
            rules=rules,
        )


def test_invalid_weekend_factor_is_rejected():
    with pytest.raises(ValueError, match="incremento"):
        TariffRules(
            {},
            Decimal("1"),
            {},
            {},
            "MXN",
        )


def test_invalid_contract_rate_is_rejected():
    with pytest.raises(ValueError, match="positiva"):
        quote(
            date(2026, 12, 13),
            date(2026, 12, 14),
            {
                date(2026, 12, 13): "baja",
            },
            customer_type="corporativo",
            contracted_nightly_rate=Decimal("0"),
            contract_valid=True,
        )


def test_unknown_channel_is_rejected():
    with pytest.raises(ValueError, match="canal"):
        quote(
            date(2026, 12, 13),
            date(2026, 12, 14),
            {
                date(2026, 12, 13): "baja",
            },
            channel="desconocido",
        )
