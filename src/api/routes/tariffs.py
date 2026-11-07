"""Administración de parámetros y cotización trazable RN-13 / US-03.

Se prohíbe inventar temporadas y multiplicadores: deben configurarse por gerencia.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.core.security import StaffIdentity, require_roles
from src.domain.reservations.pricing import TariffRules, TariffCalculationService
from src.domain.reservations.value_objects import StayPeriod
from src.domain.reservations.entities import ReservationStatus
from src.infrastructure.database.models.reservation_model import ReservationModel
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.models.tariff_model import TariffConfigurationModel, ReservationQuoteModel
from src.infrastructure.database.models.staff_model import BusinessAuditModel
from src.api.routes.staff_operations import record_audit

router=APIRouter()

class SeasonSpan(BaseModel):
    name: str = Field(pattern='^(alta|baja)$')
    start: date
    end: date  # intervalo inclusivo
    @model_validator(mode='after')
    def valid_span(self):
        if self.end < self.start:
            raise ValueError('Rango de temporada inválido.')
        return self

class TariffConfigRequest(BaseModel):
    currency: str = Field(default='MXN', pattern='^MXN$')
    bar_by_room_and_season: dict[str, Decimal]  # "Estándar|alta": 1800
    weekend_multiplier: Decimal = Field(gt=1)
    channel_multipliers: dict[str, Decimal]
    customer_multipliers: dict[str, Decimal]
    seasons: list[SeasonSpan]

    @model_validator(mode='after')
    def check_values(self):
        if not self.seasons or not self.bar_by_room_and_season:
            raise ValueError('Configura temporadas y tarifas BAR.')
        for key, value in self.bar_by_room_and_season.items():
            parts=key.rsplit('|',1)
            if len(parts)!=2 or not parts[0] or parts[1] not in ('alta','baja') or not value.is_finite() or value<=0:
                raise ValueError('BAR inválida; usa Tipo|alta o Tipo|baja.')
        for factor in (*self.channel_multipliers.values(),*self.customer_multipliers.values()):
            if not factor.is_finite() or factor<=0:
                raise ValueError('Los factores deben ser positivos.')
        days=set()
        for span in self.seasons:
            d=span.start
            while d<=span.end:
                if d in days:
                    raise ValueError('Temporadas superpuestas.')
                days.add(d)
                d+=timedelta(days=1)
                if len(days)>3660:
                    raise ValueError('El calendario configurado supera diez años.')
        return self

class ReservationQuoteRequest(BaseModel):
    channel: str = Field(min_length=1, max_length=40)
    customer_type: str = Field(min_length=1, max_length=40)
    guest_accepted: bool


def active_config(session):
    record=session.scalar(select(TariffConfigurationModel).order_by(TariffConfigurationModel.created_at.desc(),TariffConfigurationModel.id.desc()).limit(1))
    if record is None:
        raise HTTPException(status_code=409, detail='Gerencia debe configurar primero las tarifas RN-13.')
    return TariffConfigRequest.model_validate(record.payload)


def compute_quote(session, room_type, period, channel, customer_type):
    config=active_config(session)
    seasons={}
    for span in config.seasons:
        day=span.start
        while day<=span.end:
            seasons[day]=span.name
            day+=timedelta(days=1)
    rules=TariffRules(
        bar_by_room_and_season={tuple(k.rsplit('|',1)):v for k,v in config.bar_by_room_and_season.items()},
        weekend_multiplier=config.weekend_multiplier,
        channel_multipliers=config.channel_multipliers,
        customer_multipliers=config.customer_multipliers,
        currency=config.currency,
    )
    return TariffCalculationService().quote(
        stay_period=period,room_type=room_type,channel=channel,
        customer_type=customer_type,season_by_date=seasons,rules=rules,
    )

@router.post('/configuration',status_code=201)
def set_tariffs(
    data:TariffConfigRequest,
    actor:StaffIdentity=Depends(require_roles('MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        record=TariffConfigurationModel(
            payload=data.model_dump(mode='json'), authorized_by=actor.id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        session.flush()
        record_audit(session,actor,'TARIFF_CONFIGURED','tariff_configuration',record.id)
        session.commit()
        return {'configuration_id':record.id,'currency':data.currency}
    except Exception:
        session.rollback()
        raise

@router.get('/quote')
def quote_room(
    room_type:str, check_in:date, check_out:date, channel:str, customer_type:str,
    actor:StaffIdentity=Depends(require_roles('RESERVATIONS','RECEPTION','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        q=compute_quote(session,room_type,StayPeriod(check_in,check_out),channel,customer_type)
        return {'room_type':q.room_type,'currency':q.currency,'total':q.total,
                'nights':[{'day':n.day,'season':n.season,'amount':n.amount} for n in q.nights]}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc

@router.post('/reservations/{reservation_id}/accept-quote',status_code=201)
def accept_reservation_quote(
    reservation_id:UUID,data:ReservationQuoteRequest,
    actor:StaffIdentity=Depends(require_roles('RESERVATIONS','RECEPTION','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    try:
        if not data.guest_accepted:
            raise ValueError('El huésped debe aceptar la cotización antes de registrarla.')
        reservation=session.scalar(select(ReservationModel).where(ReservationModel.id==reservation_id).with_for_update())
        if reservation is None:
            raise HTTPException(status_code=404,detail='La reserva no existe.')
        if reservation.status!=ReservationStatus.REQUESTED:
            raise ValueError('Solo puede aceptar tarifa en una reserva solicitada.')
        if session.get(ReservationQuoteModel,reservation_id):
            raise ValueError('La reserva ya cuenta con tarifa aceptada.')
        room=session.get(RoomModel,reservation.room_id)
        if room is None:
            raise ValueError('La habitación no existe.')
        quote=compute_quote(session,room.room_type,StayPeriod(reservation.check_in,reservation.check_out),data.channel,data.customer_type)
        record=ReservationQuoteModel(reservation_id=reservation_id,currency=quote.currency,
            channel=quote.channel,customer_type=quote.customer_type,
            first_night=quote.nights[0].amount,total=quote.total,
            nightly_breakdown=[{'day':n.day.isoformat(),'season':n.season,'amount':str(n.amount)} for n in quote.nights],
            guest_accepted=True,authorized_by=actor.id,accepted_at=datetime.now(timezone.utc))
        session.add(record)
        record_audit(session,actor,'RESERVATION_QUOTE_ACCEPTED','reservation',reservation_id,
                     {'currency':quote.currency,'total':str(quote.total)})
        session.commit()
        return {'reservation_id':reservation_id,'total':quote.total,'currency':quote.currency,
                'first_night':quote.nights[0].amount}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
