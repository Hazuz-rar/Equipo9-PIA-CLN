from dataclasses import dataclass
from enum import Enum

from src.domain.rooms.value_objects import (
    Capacity,
    Money,
    RoomNumber,
)


class RoomStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    OUT_OF_ORDER = "OUT_OF_ORDER"


@dataclass
class Room:
    number: RoomNumber
    room_type: str
    capacity: Capacity
    base_rate: Money
    status: RoomStatus = RoomStatus.AVAILABLE

    def __post_init__(self) -> None:
        self.room_type = self.room_type.strip()

        if not self.room_type:
            raise ValueError("El tipo de habitación es obligatorio.")

        if len(self.room_type) > 50:
            raise ValueError(
                "El tipo de habitación no puede superar 50 caracteres."
            )

    def mark_occupied(self) -> None:
        if self.status != RoomStatus.AVAILABLE:
            raise ValueError(
                "Solo una habitación disponible puede ocuparse."
            )

        self.status = RoomStatus.OCCUPIED

    def mark_available(self) -> None:
        if self.status != RoomStatus.OCCUPIED:
            raise ValueError(
                "Solo una habitación ocupada puede liberarse."
            )

        self.status = RoomStatus.AVAILABLE

    def mark_out_of_order(self) -> None:
        if self.status == RoomStatus.OCCUPIED:
            raise ValueError(
                "No se puede poner fuera de servicio una habitación ocupada."
            )

        self.status = RoomStatus.OUT_OF_ORDER