"""US-11/US-12: reasignar habitación y ampliar estancia en una transacción."""
from datetime import date, datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.routes.staff_operations import record_audit
from src.api.routes.tariffs import compute_quote
from src.core.security import StaffIdentity, require_roles
from src.domain.reservations.value_objects import RoomId, ReservationId, StayPeriod
from src.domain.reservations.entities import ReservationStatus
from src.domain.rooms.entities import RoomStatus
from src.infrastructure.repositories.sqlalchemy_reservation_repository import SQLAlchemyReservationRepository
from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
from src.infrastructure.repositories.sqlalchemy_folio_repository import SQLAlchemyFolioRepository
from src.infrastructure.database.models.tariff_model import ReservationQuoteModel

router=APIRouter()

class RoomChangeRequest(BaseModel):
    new_room_id:UUID
    reason:str=Field(min_length=5,max_length=500)

class ExtensionRequest(BaseModel):
    new_check_out:date
    guest_accepted:bool
    reason:str=Field(min_length=5,max_length=500)

@router.post('/{reservation_id}/change-room')
def change_room(
    reservation_id:UUID,data:RoomChangeRequest,
    actor:StaffIdentity=Depends(require_roles('RECEPTION','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        repo=SQLAlchemyReservationRepository(session)
        reservation=repo.get_for_update(ReservationId(reservation_id))
        if reservation is None:
            raise HTTPException(status_code=404,detail='La reserva no existe.')
        if reservation.status!=ReservationStatus.CHECK_IN:
            raise ValueError('Solo se cambia habitación durante una estancia activa.')
        old_id=reservation.room_id.value
        if old_id==data.new_room_id:
            raise ValueError('La habitación de destino debe ser diferente.')
        # Bloqueos deterministas para evitar colisión entre canales y dos cambios simultáneos.
        for rid in sorted((old_id,data.new_room_id)):
            repo.lock_room(RoomId(rid))
        rooms=SQLAlchemyRoomRepository(session)
        old=rooms.get_for_update(RoomId(old_id))
        new=rooms.get_for_update(RoomId(data.new_room_id))
        if old is None or new is None:
            raise ValueError('La habitación de origen o destino no existe.')
        if old.status!=RoomStatus.OCCUPIED or not new.can_accept_reservation():
            raise ValueError('Habitación de origen/destino en estado no permitido.')
        if repo.find_active_by_room_and_period(
            RoomId(data.new_room_id),reservation.stay_period,reservation.id,
        ):
            raise ValueError('La habitación de destino está reservada para esas fechas.')
        folio=SQLAlchemyFolioRepository(session).get_by_reservation_id_for_update(reservation_id)
        if folio is None or folio.status.value!='ABIERTO':
            raise ValueError('Debe existir un folio abierto para cambiar habitación.')
        old.mark_dirty()
        new.mark_occupied()
        rooms.update(RoomId(old_id),old)
        rooms.update(RoomId(data.new_room_id),new)
        reservation.room_id=RoomId(data.new_room_id)
        repo.update(reservation)
        record_audit(session,actor,'ROOM_CHANGED','reservation',reservation_id,
                     {'from_room':str(old_id),'to_room':str(data.new_room_id),'reason':data.reason.strip()})
        session.commit()
        return {'reservation_id':reservation_id,'old_room_id':old_id,'new_room_id':data.new_room_id,
                'old_room_status':'DIRTY','new_room_status':'OCCUPIED'}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/{reservation_id}/extend')
def extend_stay(
    reservation_id:UUID,data:ExtensionRequest,
    actor:StaffIdentity=Depends(require_roles('MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        if not data.guest_accepted:
            raise ValueError('El huésped debe aceptar la tarifa de las noches adicionales.')
        repo=SQLAlchemyReservationRepository(session)
        reservation=repo.get_for_update(ReservationId(reservation_id))
        if reservation is None:
            raise HTTPException(status_code=404,detail='La reserva no existe.')
        if reservation.status not in (ReservationStatus.CONFIRMED,ReservationStatus.CHECK_IN):
            raise ValueError('Solo puede extenderse una reserva confirmada o estancia activa.')
        old_out=reservation.stay_period.check_out
        if data.new_check_out<=old_out:
            raise ValueError('La extensión debe agregar por lo menos una noche.')
        quote=session.get(ReservationQuoteModel,reservation_id)
        if quote is None:
            raise ValueError('Falta tarifa aceptada de la estancia original.')
        new_period=StayPeriod(reservation.stay_period.check_in,data.new_check_out)
        repo.lock_room(reservation.room_id)
        if repo.find_active_by_room_and_period(reservation.room_id,new_period,reservation.id):
            raise ValueError('Hay otra reserva para las fechas de extensión.')
        room=SQLAlchemyRoomRepository(session).get_for_update(reservation.room_id)
        if room is None or room.status not in (RoomStatus.AVAILABLE,RoomStatus.INSPECTED,RoomStatus.OCCUPIED):
            raise ValueError('La habitación no permite ampliar estancia.')
        new_nights=compute_quote(session,room.room_type,StayPeriod(old_out,data.new_check_out),
                                 quote.channel,quote.customer_type)
        if new_nights.currency!=quote.currency:
            raise ValueError('No se puede cambiar de moneda al extender la estancia.')
        quote.nightly_breakdown.extend([
            {'day':n.day.isoformat(),'season':n.season,'amount':str(n.amount)} for n in new_nights.nights
        ])
        quote.total+=new_nights.total
        reservation.stay_period=new_period
        repo.update(reservation)
        record_audit(session,actor,'STAY_EXTENDED','reservation',reservation_id,
                     {'previous_checkout':old_out.isoformat(),'new_checkout':data.new_check_out.isoformat(),
                      'added_amount':str(new_nights.total),'reason':data.reason.strip()})
        session.commit()
        return {'reservation_id':reservation_id,'new_check_out':data.new_check_out,
                'added_total':new_nights.total,'updated_total':quote.total,'currency':quote.currency}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.get('/{reservation_id}/possible-duplicates')
def possible_duplicates(
    reservation_id:UUID,
    actor:StaffIdentity=Depends(require_roles('RESERVATIONS','RECEPTION','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    from sqlalchemy import select
    from src.infrastructure.database.models.reservation_model import ReservationModel
    record=session.get(ReservationModel,reservation_id)
    if record is None:
        raise HTTPException(status_code=404,detail='Reserva inexistente.')
    matches=list(session.scalars(select(ReservationModel).where(
        ReservationModel.id!=record.id,
        ReservationModel.guest_id==record.guest_id,
        ReservationModel.check_in<record.check_out,
        ReservationModel.check_out>record.check_in,
        ReservationModel.status.in_((ReservationStatus.REQUESTED,ReservationStatus.CONFIRMED,ReservationStatus.CHECK_IN)),
    )))
    return {'reservation_id':reservation_id,'possible_duplicate_ids':[r.id for r in matches],
            'warning':bool(matches),'note':'Coincidencia por mismo guest_id y fechas, no comparación por similitud de contacto.'}
