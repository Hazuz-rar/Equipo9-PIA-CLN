"""Puerto de lectura de habitación para confirmar una reserva (ADR-002/004)."""

from typing import Protocol

from src.domain.rooms.entities import Room
from src.domain.reservations.value_objects import RoomId


class RoomRepository(Protocol):
    def get_by_id(self, room_id: RoomId) -> Room | None: ...

    def get_for_update(self, room_id: RoomId) -> Room | None: ...

    def update(self, room_id: RoomId, room: Room) -> None: ...
