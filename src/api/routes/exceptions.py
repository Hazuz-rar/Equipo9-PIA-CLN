"""RN-04/RN-05: estado, penalizaciones devengadas y cobro PENDIENTE de pasarela.

Una anotación de deuda nunca representa un cargo ejecutado ni un reembolso pagado.
"""
from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.routes.staff_operations import hotel_zone, record_audit
from src.core.security import StaffIdentity, require_roles
from src.domain.reservations.entities import ReservationStatus
from src.domain.reservations.policies import individual_cancellation_penalty_nights
from src.domain.reservations.value_objects import ReservationId
from src.infrastructure.database.models.exception_model import (
    ReservationFinancialEventModel, ReservationGuaranteeModel, AvailabilityOutboxModel,
)
from src.infrastructure.database.models.tariff_model import ReservationQuoteModel
from src.infrastructure.repositories.sqlalchemy_reservation_repository import SQLAlchemyReservationRepository

router=APIRouter()

class GuaranteeRequest(BaseModel):
    method: str = Field(min_length=3, max_length=80)
    external_reference: str = Field(min_length=3, max_length=255,
        description='Referencia tokenizada externa; NO tarjeta/CVV.')


def queue_availability(session, reservation_id, action, room_id):
    session.add(AvailabilityOutboxModel(
        reservation_id=reservation_id, action=action,
        payload={'room_id':str(room_id), 'reservation_id':str(reservation_id)},
        published=False, created_at=datetime.now(timezone.utc),
    ))

@router.post('/reservations/{reservation_id}/guarantee',status_code=201)
def record_guarantee(
    reservation_id: UUID, data: GuaranteeRequest,
    actor:StaffIdentity=Depends(require_roles('RECEPTION','RESERVATIONS','FINANCE','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session: Session=Depends(get_db),
):
    from src.infrastructure.database.models.reservation_model import ReservationModel
    from src.domain.reservations.entities import ReservationStatus
    try:
        res=session.scalar(select(ReservationModel).where(ReservationModel.id==reservation_id).with_for_update())
        if res is None:
            raise HTTPException(status_code=404,detail='Reserva inexistente.')
        if res.status not in (ReservationStatus.REQUESTED,ReservationStatus.CONFIRMED):
            raise ValueError('Solo se registra garantía para reserva pendiente o confirmada.')
        if session.get(ReservationGuaranteeModel,reservation_id):
            raise ValueError('Ya existe constancia de garantía.')
        # La referencia debe ser token de pasarela, no PAN; sin pasarela no se verifica el cobro.
        digits=''.join(ch for ch in data.external_reference if ch.isdigit())
        if 12 <= len(digits) <= 19:
            raise ValueError('No introduzcas números de tarjeta; usa una referencia tokenizada.')
        session.add(ReservationGuaranteeModel(
            reservation_id=reservation_id, method=data.method,
            external_reference=data.external_reference, verified_by=actor.id,
            recorded_at=datetime.now(timezone.utc),
        ))
        record_audit(session,actor,'GUARANTEE_RECORDED','reservation',reservation_id, {'method':data.method})
        session.commit()
        return {'reservation_id':reservation_id,'guarantee_recorded':True}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/reservations/{reservation_id}/cancel-policy')
def cancellation_with_policy(
    reservation_id:UUID,
    actor:StaffIdentity=Depends(require_roles('RESERVATIONS','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    zone=hotel_zone()
    try:
        repo=SQLAlchemyReservationRepository(session)
        reservation=repo.get_for_update(ReservationId(reservation_id))
        if reservation is None:
            raise HTTPException(status_code=404,detail='La reserva no existe.')
        if reservation.status!=ReservationStatus.CONFIRMED:
            raise ValueError('La política de cancelación aplica a una reserva confirmada.')
        terms=session.get(ReservationQuoteModel,reservation_id)
        if terms is None:
            raise ValueError('Falta tarifa confirmada para liquidar RN-04.')
        arrival=datetime.combine(reservation.stay_period.check_in,time(15),tzinfo=zone)
        nights=individual_cancellation_penalty_nights(arrival,datetime.now(timezone.utc))
        amount=Decimal(nights)*terms.first_night
        reservation.cancel_with_policy()
        repo.update(reservation)
        event=ReservationFinancialEventModel(
            reservation_id=reservation_id,event_type='CANCELLATION_PENALTY',
            amount=amount,currency=terms.currency,
            settlement_status='PENDING_GATEWAY' if amount>0 else 'NO_CHARGE',
            actor_id=actor.id,occurred_at=datetime.now(timezone.utc),
        )
        session.add(event)
        queue_availability(session,reservation_id,'CANCELLED',reservation.room_id.value)
        record_audit(session,actor,'RESERVATION_CANCELLED','reservation',reservation_id,
                     {'penalty_nights':nights,'penalty':str(amount),'collection_pending':amount>0})
        session.commit()
        return {'reservation_id':reservation_id,'status':'CANCELADA',
                'penalty_nights':nights,'penalty':amount,'currency':terms.currency,
                'settlement_status':event.settlement_status,
                'notice':'Los cargos/reembolsos requieren integración externa; no se han cobrado.'}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/reservations/{reservation_id}/no-show')
def mark_no_show(
    reservation_id:UUID,
    actor:StaffIdentity=Depends(require_roles('FINANCE','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    zone=hotel_zone()
    try:
        repo=SQLAlchemyReservationRepository(session)
        reservation=repo.get_for_update(ReservationId(reservation_id))
        if reservation is None:
            raise HTTPException(status_code=404,detail='La reserva no existe.')
        if reservation.status!=ReservationStatus.CONFIRMED:
            raise ValueError('Solo una reserva confirmada puede ser no-show.')
        now=datetime.now(timezone.utc).astimezone(zone)
        deadline=datetime.combine(reservation.stay_period.check_in,time(23,59),tzinfo=zone)
        if now<deadline:
            raise ValueError('No se permite No-Show antes de las 23:59 del día de llegada.')
        guarantee=session.get(ReservationGuaranteeModel,reservation_id)
        terms=session.get(ReservationQuoteModel,reservation_id)
        if guarantee is not None and terms is None:
            raise ValueError('No se conoce la primera noche; no puede registrarse cobro RN-05.')
        amount=terms.first_night if guarantee is not None else Decimal('0.00')
        currency=terms.currency if terms is not None else 'MXN'
        reservation.mark_no_show()
        repo.update(reservation)
        event=ReservationFinancialEventModel(
            reservation_id=reservation_id,event_type='NO_SHOW_PENALTY',
            amount=amount,currency=currency,
            settlement_status='PENDING_GATEWAY' if amount>0 else 'NO_GUARANTEE',
            actor_id=actor.id,occurred_at=datetime.now(timezone.utc),
        )
        session.add(event)
        queue_availability(session,reservation_id,'NO_SHOW',reservation.room_id.value)
        record_audit(session,actor,'NO_SHOW','reservation',reservation_id,
                     {'guarantee_recorded':guarantee is not None,'penalty':str(amount)})
        session.commit()
        return {'reservation_id':reservation_id,'status':'NO_SHOW',
                'penalty':amount,'currency':currency,'settlement_status':event.settlement_status,
                'note':'Cobro por pasarela no ejecutado. Atención a garantía y saldos pendientes.'}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.get('/channels/pending')
def pending_outbox(
    actor:StaffIdentity=Depends(require_roles('RESERVATIONS','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    events=session.scalars(select(AvailabilityOutboxModel)
        .where(AvailabilityOutboxModel.published.is_(False))
        .order_by(AvailabilityOutboxModel.created_at.asc()).limit(100)).all()
    return [{'id':e.id,'reservation_id':e.reservation_id,'action':e.action,'payload':e.payload,
             'published':e.published} for e in events]
