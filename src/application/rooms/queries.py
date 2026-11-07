
"""Consulta de disponibilidad: US-02 y ADR-005."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from src.domain.reservations.value_objects import (
    StayPeriod,
)


@dataclass(frozen=True)
class AvailableRoom:
    id: UUID
    number: str
    room_type: str
    capacity: int
    base_rate: Decimal
    currency: str


class RoomAvailabilityReader(Protocol):
    def find_available(
        self,
        period: StayPeriod,
        room_type: str | None,
        guests: int,
    ) -> list[AvailableRoom]:
        ...


class RoomAvailabilityService:
    def __init__(
        self,
        reader: RoomAvailabilityReader,
    ) -> None:
        self.reader = reader

    def search(
        self,
        *,
        check_in: date,
        check_out: date,
        room_type: str | None = None,
        guests: int = 1,
    ) -> list[AvailableRoom]:

        if isinstance(guests, bool) or guests < 1:
            raise ValueError(
                "La cantidad de huéspedes debe ser positiva."
            )

        if room_type is not None and not room_type.strip():
            raise ValueError(
                "El tipo de habitación no puede estar vacío."
            )

        period = StayPeriod(
            check_in=check_in,
            check_out=check_out,
        )

        return self.reader.find_available(
            period,
            room_type.strip() if room_type else None,
            guests,
        )
