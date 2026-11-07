"""Unit of Work para limpieza y su evento auditable: ADR-004.

La identidad del actor debe venir de un servicio de autenticación confiable;
este módulo solo se utiliza internamente hasta incorporar esa integración.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from src.domain.rooms.entities import RoomStatus
from src.infrastructure.database.models.room_cleaning_event_model import (
    RoomCleaningEventModel,
)
from src.infrastructure.repositories.sqlalchemy_room_repository import (
    SQLAlchemyRoomRepository,
)


class SQLAlchemyCleaningAuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def add_cleaning_event(
        self, room_id: UUID, actor_id: UUID,
        from_status: RoomStatus, to_status: RoomStatus,
        occurred_at: datetime,
    ) -> None:
        self.session.add(
            RoomCleaningEventModel(
                id=uuid4(),
                room_id=room_id,
                actor_id=actor_id,
                actor_role="HOUSEKEEPING",
                previous_status=from_status.value,
                new_status=to_status.value,
                occurred_at=occurred_at,
            )
        )
        self.session.flush()


class SQLAlchemyRoomCleaningUnitOfWork:
    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory
        self.session = None
        self._committed = False

    def __enter__(self):
        self.session = self.session_factory()
        try:
            self.rooms = SQLAlchemyRoomRepository(self.session)
            self.audit = SQLAlchemyCleaningAuditRepository(self.session)
        except Exception:
            self.session.close()
            raise
        return self

    def commit(self) -> None:
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if not self._committed:
                self.session.rollback()
        finally:
            self.session.close()
