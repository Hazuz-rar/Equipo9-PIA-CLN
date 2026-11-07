
from collections.abc import Generator

from sqlalchemy.orm import Session

from src.infrastructure.repositories.sqlalchemy_room_repository import (
    SQLAlchemyRoomRepository,
)

from src.infrastructure.database.session import SessionLocal
from src.infrastructure.repositories.sqlalchemy_reservation_repository import (
    SQLAlchemyReservationRepository,
)
from src.application.reservations.services import ReservationService


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()



def get_reservation_service(
    session: Session,
) -> ReservationService:
    reservation_repository = SQLAlchemyReservationRepository(
        session
    )

    room_repository = SQLAlchemyRoomRepository(
        session
    )

    return ReservationService(
        reservation_repository,
        room_repository,
    )

