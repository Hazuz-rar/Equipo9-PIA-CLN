"""Unit of Work para recepción: una sesión, un COMMIT o ROLLBACK.

En PostgreSQL los repositorios usan SELECT FOR UPDATE. SQLite solo prueba
la secuencia funcional, no la concurrencia real.
"""
from collections.abc import Callable

from sqlalchemy.orm import Session

from src.infrastructure.repositories.sqlalchemy_reservation_repository import (
    SQLAlchemyReservationRepository,
)
from src.infrastructure.repositories.sqlalchemy_room_repository import (
    SQLAlchemyRoomRepository,
)
from src.infrastructure.repositories.sqlalchemy_folio_repository import (
    SQLAlchemyFolioRepository,
)
from src.infrastructure.repositories.sqlalchemy_check_in_repository import (
    SQLAlchemyCheckInRepository,
)


class SQLAlchemyCheckInUnitOfWork:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        encryption_key: str,
        actor_id=None,
        audit_action=None,
        audit_entity_id=None,
    ) -> None:
        self.session_factory = session_factory
        self.encryption_key = encryption_key
        self.session = None
        self._committed = False
        self.actor_id = actor_id
        self.audit_action = audit_action
        self.audit_entity_id = audit_entity_id

    def __enter__(self):
        self.session = self.session_factory()
        try:
            self.reservations = SQLAlchemyReservationRepository(self.session)
            self.rooms = SQLAlchemyRoomRepository(self.session)
            self.folios = SQLAlchemyFolioRepository(self.session)
            self.records = SQLAlchemyCheckInRepository(
                self.session, self.encryption_key
            )
        except Exception:
            self.session.close()
            raise
        return self

    def last_night_rate(self, reservation_id):
        from decimal import Decimal
        from src.infrastructure.database.models.tariff_model import ReservationQuoteModel
        quote = self.session.get(ReservationQuoteModel, reservation_id)
        if quote is None or not quote.nightly_breakdown:
            return None
        return Decimal(quote.nightly_breakdown[-1]['amount'])

    def commit(self) -> None:
        if self.actor_id is not None:
            from src.infrastructure.database.models.staff_model import BusinessAuditModel
            from datetime import datetime, timezone
            self.session.add(BusinessAuditModel(
                actor_id=self.actor_id, action=self.audit_action,
                entity_type='reservation', entity_id=self.audit_entity_id,
                details={}, occurred_at=datetime.now(timezone.utc),
            ))
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if not self._committed:
                self.session.rollback()
        finally:
            self.session.close()
