from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True)
class CreateReservationCommand:
    guest_id: UUID
    room_id: UUID
    check_in: date
    check_out: date


@dataclass(frozen=True)
class ConfirmReservationCommand:
    reservation_id: UUID


@dataclass(frozen=True)
class CancelReservationCommand:
    reservation_id: UUID