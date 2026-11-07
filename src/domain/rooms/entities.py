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
    DIRTY = "DIRTY"  # US-13: salida, pendiente de limpieza
    INSPECTED = "INSPECTED"  # RF-07: habitación revisada y lista
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

    def can_accept_reservation(self) -> bool:
        """Estado operativo conservador antes de confirmar (RF-07)."""
        return self.status in (RoomStatus.AVAILABLE, RoomStatus.INSPECTED)

    def mark_occupied(self) -> None:
        if not self.can_accept_reservation():
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
    def mark_dirty(self) -> None:
        """US-13: después de la salida debe limpiarse, no reservarse de inmediato."""
        if self.status != RoomStatus.OCCUPIED:
            raise ValueError("Solo una habitación ocupada puede pasar a sucia.")
        self.status = RoomStatus.DIRTY

    def mark_clean(self) -> None:
        """US-15: limpieza completada; pendiente añadir trazabilidad y permisos."""
        if self.status != RoomStatus.DIRTY:
            raise ValueError("Solo una habitación sucia puede limpiarse.")
        self.status = RoomStatus.AVAILABLE

    def restore_after_maintenance(self, requires_cleaning: bool) -> None:
        """US-21: gerencia autoriza la restitución tras resolver incidencia."""
        if self.status != RoomStatus.OUT_OF_ORDER:
            raise ValueError('Solo una habitación fuera de servicio puede reactivarse.')
        self.status = RoomStatus.DIRTY if requires_cleaning else RoomStatus.AVAILABLE

    def mark_inspected(self) -> None:
        """RF-07: mantener la marca de habitación inspeccionada antes de su ocupación."""
        if self.status != RoomStatus.AVAILABLE:
            raise ValueError('Solo una habitación disponible puede marcarse inspeccionada.')
        self.status = RoomStatus.INSPECTED
