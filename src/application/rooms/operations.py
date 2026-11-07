"""US-14 y US-15: limpieza con permisos y auditoría interna.

IMPORTANTE: el rol e identificador deben proceder de una identidad autenticada.
Este caso de uso NO se expone como API pública hasta disponer de autenticación.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Protocol
from uuid import UUID

from src.domain.reservations.value_objects import RoomId
from src.domain.rooms.entities import Room, RoomStatus


class HotelStaffRole(str, Enum):
    HOUSEKEEPING = "HOUSEKEEPING"
    RECEPTION = "RECEPTION"
    MANAGER_RECEPTION = "MANAGER_RECEPTION"
    MANAGER_OPERATIONS = "MANAGER_OPERATIONS"


@dataclass(frozen=True)
class PendingCleaningRoom:
    id: UUID
    number: str
    room_type: str


class CleaningRoomRepository(Protocol):
    def list_dirty(self) -> list[PendingCleaningRoom]: ...
    def get_for_update(self, room_id: RoomId) -> Room | None: ...
    def update(self, room_id: RoomId, room: Room) -> None: ...


class CleaningAuditRepository(Protocol):
    def add_cleaning_event(
        self, room_id: UUID, actor_id: UUID,
        from_status: RoomStatus, to_status: RoomStatus,
        occurred_at: datetime,
    ) -> None: ...


class CleaningUnitOfWork(Protocol):
    rooms: CleaningRoomRepository
    audit: CleaningAuditRepository
    def __enter__(self) -> "CleaningUnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class HousekeepingService:
    def __init__(self, uow_factory: Callable[[], CleaningUnitOfWork]):
        self.uow_factory = uow_factory

    @staticmethod
    def _authorize(role: HotelStaffRole) -> None:
        # Un simple rol declarado no reemplaza autenticación; uso interno.
        if role is not HotelStaffRole.HOUSEKEEPING:
            raise PermissionError("Se requiere el rol de Limpieza.")

    def list_pending(self, role: HotelStaffRole) -> list[PendingCleaningRoom]:
        self._authorize(role)
        with self.uow_factory() as uow:
            return uow.rooms.list_dirty()

    def finish_cleaning(
        self, room_id: UUID, actor_id: UUID, role: HotelStaffRole,
    ) -> RoomStatus:
        self._authorize(role)
        if not isinstance(room_id, UUID) or not isinstance(actor_id, UUID):
            raise ValueError("Se requieren identificadores UUID válidos.")

        with self.uow_factory() as uow:
            identity = RoomId(room_id)
            room = uow.rooms.get_for_update(identity)
            if room is None:
                raise ValueError("La habitación no existe.")

            previous = room.status
            room.mark_clean()  # El dominio solo acepta DIRTY -> AVAILABLE.
            uow.rooms.update(identity, room)
            uow.audit.add_cleaning_event(
                room_id=room_id,
                actor_id=actor_id,
                from_status=previous,
                to_status=room.status,
                occurred_at=datetime.now(timezone.utc),
            )
            uow.commit()
            return room.status
