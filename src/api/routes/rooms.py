
"""API de consulta de habitaciones disponibles."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.application.rooms.queries import (
    RoomAvailabilityService,
)
from src.infrastructure.repositories.sqlalchemy_room_repository import (
    SQLAlchemyRoomRepository,
)


router = APIRouter()


class AvailableRoomResponse(BaseModel):
    id: UUID
    number: str
    room_type: str
    capacity: int
    base_rate: Decimal
    currency: str


@router.get(
    "/available",
    response_model=list[AvailableRoomResponse],
)
def list_available_rooms(
    check_in: date,
    check_out: date,
    room_type: str | None = None,
    guests: int = Query(default=1, ge=1),
    session: Session = Depends(get_db),
):
    service = RoomAvailabilityService(
        SQLAlchemyRoomRepository(session)
    )

    try:
        return service.search(
            check_in=check_in,
            check_out=check_out,
            room_type=room_type,
            guests=guests,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
