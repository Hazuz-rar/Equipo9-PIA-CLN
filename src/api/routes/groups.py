"""US-22: bloqueos grupales/depósitos manualmente verificados; sin pasarela."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.routes.staff_operations import record_audit, hotel_zone
from src.api.routes.tariffs import compute_quote
from src.core.security import StaffIdentity, require_roles
from src.domain.reservations.value_objects import StayPeriod, RoomId
from src.domain.reservations.groups import required_group_deposit, group_deposit_refundable
from src.infrastructure.database.models.group_model import GroupBookingModel, GroupHeldRoomModel
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
from src.infrastructure.repositories.sqlalchemy_reservation_repository import SQLAlchemyReservationRepository

router=APIRouter()
GROUP_ROLES=('RESERVATIONS','MANAGER_RECEPTION','MANAGER_OPERATIONS')

class GroupCreate(BaseModel):
    organizer:str=Field(min_length=2,max_length=150)
    contract_reference:str=Field(min_length=5,max_length=150)
    room_ids:list[UUID]=Field(min_length=10)
    check_in:date
    check_out:date
    deposit_due_at:datetime
    channel:str=Field(min_length=1,max_length=40)
    customer_type:str=Field(min_length=1,max_length=40)

class GroupDeposit(BaseModel):
    amount:Decimal=Field(gt=0)
    receipt_reference:str=Field(min_length=5,max_length=150)

@router.post('',status_code=201)
def create_group(
    data:GroupCreate,
    actor:StaffIdentity=Depends(require_roles(*GROUP_ROLES)),
    session:Session=Depends(get_db),
):
    try:
        period=StayPeriod(data.check_in,data.check_out)
        if len(set(data.room_ids))!=len(data.room_ids):
            raise ValueError('Las habitaciones del grupo deben ser distintas.')
        if data.deposit_due_at.tzinfo is None or data.deposit_due_at.utcoffset() is None:
            raise ValueError('El plazo de depósito requiere zona horaria.')
        if data.deposit_due_at<=datetime.now(timezone.utc):
            raise ValueError('El plazo para depósito debe estar en el futuro.')
        reservation_repo=SQLAlchemyReservationRepository(session)
        for room_id in sorted(data.room_ids):
            reservation_repo.lock_room(RoomId(room_id))
        available={r.id:r for r in SQLAlchemyRoomRepository(session).find_available(period,None,1)}
        if any(room_id not in available for room_id in data.room_ids):
            raise ValueError('Una o más habitaciones no están disponibles para el grupo.')
        total=Decimal('0.00')
        for room_id in data.room_ids:
            quote=compute_quote(session,available[room_id].room_type,period,data.channel,data.customer_type)
            total+=quote.total
        required=required_group_deposit(len(data.room_ids),total)
        record=GroupBookingModel(organizer=data.organizer.strip(),contract_reference=data.contract_reference.strip(),
            check_in=data.check_in,check_out=data.check_out,deposit_due_at=data.deposit_due_at,
            total=total,currency='MXN',required_deposit=required,deposit_paid=Decimal('0'),status='PENDING_DEPOSIT',
            created_by=actor.id,created_at=datetime.now(timezone.utc))
        session.add(record);session.flush()
        session.add_all(GroupHeldRoomModel(group_id=record.id,room_id=id) for id in data.room_ids)
        record_audit(session,actor,'GROUP_HOLD_CREATED','group',record.id,{'rooms':len(data.room_ids)})
        session.commit()
        return {'id':record.id,'status':record.status,'total':total,'required_deposit':required,'currency':'MXN'}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/{group_id}/confirm-deposit')
def confirm_group_deposit(
    group_id:UUID, data:GroupDeposit,
    actor:StaffIdentity=Depends(require_roles(*GROUP_ROLES)),
    session:Session=Depends(get_db),
):
    try:
        group=session.scalar(select(GroupBookingModel).where(GroupBookingModel.id==group_id).with_for_update())
        if group is None:
            raise HTTPException(status_code=404,detail='Grupo inexistente.')
        if group.status!='PENDING_DEPOSIT' or datetime.now(timezone.utc)>group.deposit_due_at.replace(tzinfo=group.deposit_due_at.tzinfo or timezone.utc):
            raise ValueError('El bloqueo del grupo ya no admite confirmación.')
        if data.amount<group.required_deposit:
            raise ValueError('El depósito acreditado debe ser al menos 30 % del total.')
        group.deposit_paid=data.amount
        group.deposit_reference=data.receipt_reference
        group.status='CONFIRMED'
        record_audit(session,actor,'GROUP_DEPOSIT_RECORDED','group',group_id,
                     {'amount':str(data.amount),'method':'Comprobante verificado manualmente; sin PSP'})
        session.commit()
        return {'id':group_id,'status':'CONFIRMED','deposit_recorded':data.amount}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/{group_id}/cancel')
def cancel_group(
    group_id:UUID,
    actor:StaffIdentity=Depends(require_roles(*GROUP_ROLES)),
    session:Session=Depends(get_db),
):
    zone=hotel_zone()
    try:
        group=session.scalar(select(GroupBookingModel).where(GroupBookingModel.id==group_id).with_for_update())
        if group is None:
            raise HTTPException(status_code=404,detail='Grupo inexistente.')
        if group.status not in ('CONFIRMED','PENDING_DEPOSIT'):
            raise ValueError('El grupo ya fue cancelado.')
        refundable=group_deposit_refundable(group.check_in,datetime.now(timezone.utc).astimezone(zone).date())
        refund=group.deposit_paid if refundable else Decimal('0.00')
        group.status='CANCELLED'
        record_audit(session,actor,'GROUP_CANCELLED','group',group_id,
                     {'refund_pending':str(refund),'policy_days':7})
        session.commit()
        return {'id':group_id,'status':'CANCELLED','refundable_deposit':refund,
                'refund_status':'PENDING_MANUAL_PROCESSING' if refund>0 else 'NOT_APPLICABLE',
                'notice':'No se ha ejecutado ninguna transferencia de devolución.'}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
