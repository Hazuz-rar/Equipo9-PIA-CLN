"""RN-06/US-23: caso de reubicación coordinado con un hotel aliado.

El personal confirma manualmente la reserva externa; no es una OTA automática.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.routes.staff_operations import record_audit
from src.api.routes.exceptions import queue_availability
from src.core.security import StaffIdentity, require_roles
from src.domain.reservations.entities import ReservationStatus
from src.domain.reservations.value_objects import ReservationId
from src.domain.rooms.entities import RoomStatus
from src.infrastructure.repositories.sqlalchemy_reservation_repository import SQLAlchemyReservationRepository
from src.infrastructure.database.models.walk_model import WalkCaseModel
from src.infrastructure.database.models.room_model import RoomModel

router=APIRouter()

class WalkProposal(BaseModel):
    allied_hotel:str=Field(min_length=3,max_length=150)
    transport_details:str=Field(min_length=3,max_length=500)
    fare_difference:Decimal=Field(ge=0)
    courtesy_details:str=Field(min_length=3,max_length=500)

class PartnerConfirmation(BaseModel):
    partner_booking_reference:str=Field(min_length=5,max_length=200)
    similar_category_verified:bool

@router.post('/reservations/{reservation_id}/walk-plan',status_code=201)
def plan_walk(
    reservation_id:UUID,data:WalkProposal,
    actor:StaffIdentity=Depends(require_roles('RECEPTION','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        repo=SQLAlchemyReservationRepository(session)
        r=repo.get_for_update(ReservationId(reservation_id))
        if r is None:
            raise HTTPException(status_code=404,detail='Reserva inexistente.')
        if r.status!=ReservationStatus.CONFIRMED:
            raise ValueError('Solo puede prepararse walk para reserva confirmada.')
        room=session.get(RoomModel,r.room_id.value)
        if room is not None and room.status not in (RoomStatus.OUT_OF_ORDER,RoomStatus.OCCUPIED):
            raise ValueError('No hay incidencia de asignación que justifique reubicación.')
        if session.scalar(select(WalkCaseModel).where(WalkCaseModel.reservation_id==reservation_id)):
            raise ValueError('Ya hay expediente de reubicación para la reserva.')
        case=WalkCaseModel(reservation_id=reservation_id,allied_hotel=data.allied_hotel.strip(),
            transport_details=data.transport_details.strip(),fare_difference=data.fare_difference,
            courtesy_details=data.courtesy_details.strip(),state='PENDING_PARTNER',
            approved_by=actor.id,created_at=datetime.now(timezone.utc))
        session.add(case);session.flush()
        record_audit(session,actor,'WALK_PROPOSED','reservation',reservation_id,
                     {'walk_id':str(case.id),'allied_hotel':case.allied_hotel})
        session.commit()
        return {'walk_id':case.id,'reservation_id':reservation_id,'state':case.state,
                'note':'No se ha reservado habitación con el hotel aliado.'}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/walk-cases/{walk_id}/confirm-partner')
def confirm_partner(
    walk_id:UUID,data:PartnerConfirmation,
    actor:StaffIdentity=Depends(require_roles('MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        if not data.similar_category_verified:
            raise ValueError('Gerencia debe verificar categoría similar del hotel aliado.')
        case=session.scalar(select(WalkCaseModel).where(WalkCaseModel.id==walk_id).with_for_update())
        if case is None:
            raise HTTPException(status_code=404,detail='Expediente inexistente.')
        if case.state!='PENDING_PARTNER':
            raise ValueError('El expediente ya fue confirmado.')
        repo=SQLAlchemyReservationRepository(session)
        res=repo.get_for_update(ReservationId(case.reservation_id))
        if res is None or res.status!=ReservationStatus.CONFIRMED:
            raise ValueError('La reserva ya no admite reubicación.')
        res.relocate()
        repo.update(res)
        case.state='PARTNER_CONFIRMED_MANUALLY'
        case.partner_booking_reference=data.partner_booking_reference.strip()
        case.confirmed_at=datetime.now(timezone.utc)
        queue_availability(session,res.id.value,'RELOCATED',res.room_id.value)
        record_audit(session,actor,'WALK_CONFIRMED','reservation',res.id.value,
                     {'walk_id':str(walk_id),'partner_booking_reference':case.partner_booking_reference})
        session.commit()
        return {'walk_id':walk_id,'reservation_id':res.id.value,'status':res.status.value,
                'manual_partner_confirmation':True}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
