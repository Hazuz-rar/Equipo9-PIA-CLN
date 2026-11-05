
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_db, get_reservation_service
from src.api.schemas.reservation import (
    ReservationCreate,
    ReservationResponse,
    CancellationPreviewResponse,
)
from src.application.reservations.commands import (
    CancelReservationCommand,
    ConfirmReservationCommand,
    CreateReservationCommand,
)
from src.application.reservations.services import ReservationService
from src.application.ports.reservation_repository import ReservationRepository
from src.infrastructure.repositories.sqlalchemy_reservation_repository import (
    SQLAlchemyReservationRepository,
)

router = APIRouter()


def to_response(reservation) -> ReservationResponse:
    return ReservationResponse(
        id=reservation.id.value,
        guest_id=reservation.guest_id.value,
        room_id=reservation.room_id.value,
        check_in=reservation.stay_period.check_in,
        check_out=reservation.stay_period.check_out,
        status=reservation.status.value,
    )


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    data: ReservationCreate,
    session: Session = Depends(get_db),
):
    service = get_reservation_service(session)

    command = CreateReservationCommand(
        guest_id=data.guest_id,
        room_id=data.room_id,
        check_in=data.check_in,
        check_out=data.check_out,
    )

    try:
        reservation = service.create(command)
        session.commit()
        return to_response(reservation)
    except Exception:
        session.rollback()
        raise


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
)
def get_reservation(
    reservation_id: UUID,
    session: Session = Depends(get_db),
):
    repository = SQLAlchemyReservationRepository(session)
    from src.domain.reservations.value_objects import ReservationId

    reservation = repository.get_by_id(ReservationId(reservation_id))

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La reserva no existe.",
        )

    return to_response(reservation)


@router.patch(
    "/{reservation_id}/confirm",
    response_model=ReservationResponse,
)
def confirm_reservation(
    reservation_id: UUID,
    session: Session = Depends(get_db),
):
    service = get_reservation_service(session)

    try:
        reservation = service.confirm(
            ConfirmReservationCommand(reservation_id=reservation_id)
        )
        session.commit()
        return to_response(reservation)
    except ValueError as error:
        session.rollback()
        if str(error) == "La reserva no existe.":
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=409, detail=str(error))
    except Exception:
        session.rollback()
        raise


@router.patch(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
)
def cancel_reservation(
    reservation_id: UUID,
    session: Session = Depends(get_db),
):
    service = get_reservation_service(session)

    try:
        reservation = service.cancel(
            CancelReservationCommand(reservation_id=reservation_id)
        )
        session.commit()
        return to_response(reservation)
    except ValueError as error:
        session.rollback()
        if str(error) == "La reserva no existe.":
            raise HTTPException(status_code=404, detail=str(error))
        raise HTTPException(status_code=409, detail=str(error))
    except Exception:
        session.rollback()
        raise


@router.get(
    "/{reservation_id}/cancellation-preview",
    response_model=CancellationPreviewResponse,
)
def preview_individual_cancellation(
    reservation_id: UUID,
    arrival_at: datetime,
    requested_at: datetime,
    session: Session = Depends(get_db),
):
    service = get_reservation_service(session)

    try:
        nights = service.preview_individual_cancellation(
            reservation_id=reservation_id,
            arrival_at=arrival_at,
            requested_at=requested_at,
        )

        return CancellationPreviewResponse(
            reservation_id=reservation_id,
            penalty_nights=nights,
        )

    except ValueError as error:
        if str(error) == "La reserva no existe.":
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error

        if str(error) == (
            "La reserva no admite previsualización de cancelación."
        ):
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
