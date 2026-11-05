
"""Servicio de cotización: RN-13, RF-03, US-03 y ADR-003.

Los precios y factores se reciben de una configuración aprobada.
No se establecen tarifas oficiales del hotel en este módulo.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping

from src.domain.reservations.value_objects import StayPeriod


CENT = Decimal("0.01")
CONTRACT_CUSTOMERS = frozenset({"corporativo", "negociado"})


@dataclass(frozen=True)
class TariffRules:
    bar_by_room_and_season: Mapping[tuple[str, str], Decimal]
    weekend_multiplier: Decimal
    channel_multipliers: Mapping[str, Decimal]
    customer_multipliers: Mapping[str, Decimal]
    currency: str

    def __post_init__(self) -> None:
        if not self.currency or not self.currency.strip():
            raise ValueError(
                "Debe configurarse la moneda de la tarifa."
            )

        if (
            not isinstance(self.weekend_multiplier, Decimal)
            or not self.weekend_multiplier.is_finite()
            or self.weekend_multiplier <= Decimal("1")
        ):
            raise ValueError(
                "El incremento de viernes y sábado debe ser mayor que 1."
            )

        for amount in self.bar_by_room_and_season.values():
            if (
                not isinstance(amount, Decimal)
                or not amount.is_finite()
                or amount <= 0
            ):
                raise ValueError(
                    "Las tarifas BAR deben ser importes positivos."
                )

        for factor in (
            *self.channel_multipliers.values(),
            *self.customer_multipliers.values(),
        ):
            if (
                not isinstance(factor, Decimal)
                or not factor.is_finite()
                or factor <= 0
            ):
                raise ValueError(
                    "Los factores deben ser positivos."
                )


@dataclass(frozen=True)
class NightRate:
    day: date
    season: str
    amount: Decimal


@dataclass(frozen=True)
class TariffQuote:
    room_type: str
    channel: str
    customer_type: str
    nights: tuple[NightRate, ...]
    total: Decimal
    currency: str


class TariffCalculationService:
    """Calcula una cotización sin guardar ni confirmar reservas."""

    def quote(
        self,
        *,
        stay_period: StayPeriod,
        room_type: str,
        channel: str,
        customer_type: str,
        season_by_date: Mapping[date, str],
        rules: TariffRules,
        contracted_nightly_rate: Decimal | None = None,
        contract_valid: bool = False,
    ) -> TariffQuote:

        if (
            not room_type.strip()
            or not channel.strip()
            or not customer_type.strip()
        ):
            raise ValueError(
                "Se requiere habitación, canal y tipo de cliente."
            )

        contracted = customer_type in CONTRACT_CUSTOMERS

        if contracted:
            if not contract_valid or contracted_nightly_rate is None:
                raise ValueError(
                    "La tarifa corporativa o negociada requiere contrato vigente."
                )

            if (
                not isinstance(contracted_nightly_rate, Decimal)
                or not contracted_nightly_rate.is_finite()
                or contracted_nightly_rate <= 0
            ):
                raise ValueError(
                    "La tarifa del contrato debe ser positiva."
                )

        elif contracted_nightly_rate is not None or contract_valid:
            raise ValueError(
                "Los datos de contrato solo aplican a tarifas "
                "corporativas o negociadas."
            )

        else:
            if channel not in rules.channel_multipliers:
                raise ValueError(
                    "No hay un factor configurado para ese canal."
                )

            if customer_type not in rules.customer_multipliers:
                raise ValueError(
                    "No hay un factor configurado para ese tipo de cliente."
                )

        lines = []
        day = stay_period.check_in

        while day < stay_period.check_out:

            season = season_by_date.get(day)

            if season not in {"alta", "baja"}:
                raise ValueError(
                    f"Falta temporada válida para {day.isoformat()}."
                )

            if contracted:
                amount = contracted_nightly_rate

            else:
                base = rules.bar_by_room_and_season.get(
                    (room_type, season)
                )

                if base is None:
                    raise ValueError(
                        "No hay tarifa BAR para ese tipo de "
                        "habitación y temporada."
                    )

                amount = base

                # Viernes = 4, sábado = 5
                if day.weekday() in (4, 5):
                    amount *= rules.weekend_multiplier

                amount *= rules.channel_multipliers[channel]
                amount *= rules.customer_multipliers[customer_type]

            lines.append(
                NightRate(
                    day=day,
                    season=season,
                    amount=amount.quantize(
                        CENT,
                        rounding=ROUND_HALF_UP,
                    ),
                )
            )

            day += timedelta(days=1)

        nights = tuple(lines)

        return TariffQuote(
            room_type=room_type,
            channel=channel,
            customer_type=customer_type,
            nights=nights,
            total=sum(
                (line.amount for line in nights),
                Decimal("0.00"),
            ),
            currency=rules.currency,
        )
