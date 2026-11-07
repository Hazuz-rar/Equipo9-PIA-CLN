"""Lecturas CQRS de informes US-16/17; distinguir contabilidad real de estimaciones."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.core.security import StaffIdentity, require_roles
from src.domain.reservations.entities import ReservationStatus
from src.domain.rooms.entities import RoomStatus
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.models.reservation_model import ReservationModel
from src.infrastructure.database.models.folio_model import FolioPaymentModel
from src.infrastructure.database.models.tariff_model import ReservationQuoteModel

router=APIRouter()
REPORT_ROLES=('FINANCE','MANAGER_RECEPTION','MANAGER_OPERATIONS')

def room_summary(session):
    rooms=list(session.scalars(select(RoomModel)))
    total=len(rooms)
    out_of_service=sum(r.status==RoomStatus.OUT_OF_ORDER for r in rooms)
    return total, out_of_service, {status.value:sum(r.status==status for r in rooms) for status in RoomStatus}

@router.get('/daily')
def daily_report(
    target_date:date,
    actor:StaffIdentity=Depends(require_roles(*REPORT_ROLES)),
    session:Session=Depends(get_db),
):
    reservations=list(session.scalars(select(ReservationModel)))
    total,ooo,counts=room_summary(session)
    in_house=[r for r in reservations if r.check_in<=target_date<r.check_out and
              r.status in (ReservationStatus.CONFIRMED,ReservationStatus.CHECK_IN)]
    # Se informa OCUPACIÓN prevista, no ocupación histórica certificada.
    availability=max(total-ooo,0)
    occupancy=(Decimal(len({r.room_id for r in in_house}))/Decimal(availability)*100).quantize(Decimal('.01')) if availability else Decimal('0.00')
    return {
        'date':target_date,'rooms_total':total,'rooms_out_of_order_now':ooo,
        'room_status_now':counts,'estimated_occupancy_percent':occupancy,
        'arrivals':[r.id for r in reservations if r.check_in==target_date],
        'departures':[r.id for r in reservations if r.check_out==target_date],
        'note':'Ocupación estimada con reservaciones actuales. No es histórico de ocupación auditado.',
    }

@router.get('/weekly')
def weekly_report(
    start_date:date,
    actor:StaffIdentity=Depends(require_roles(*REPORT_ROLES)),
    session:Session=Depends(get_db),
):
    end_date=start_date+timedelta(days=7)
    rows=list(session.scalars(select(ReservationModel)))
    payments=list(session.scalars(select(FolioPaymentModel).where(FolioPaymentModel.recorded_at.is_not(None))))
    # 'recorded_at' solo existe en movimientos futuros; los históricos son incompletos.
    start=datetime.combine(start_date,time.min,tzinfo=timezone.utc)
    end=datetime.combine(end_date,time.min,tzinfo=timezone.utc)
    receipts=sum((p.amount for p in payments if start<=p.recorded_at.replace(tzinfo=p.recorded_at.tzinfo or timezone.utc)<end),Decimal('0'))
    cancels=sum(r.status==ReservationStatus.CANCELLED and start_date<=r.check_in<end_date for r in rows)
    no_shows=sum(r.status==ReservationStatus.NO_SHOW and start_date<=r.check_in<end_date for r in rows)
    return {
        'start_date':start_date, 'end_date_exclusive':end_date,
        'payments_recorded_in_period':receipts,'currency':'MXN',
        'cancelled_arrivals_in_period':cancels,'no_show_arrivals_in_period':no_shows,
        'adr':None,'revpar':None,
        'note':'ADR/RevPAR requieren ingresos de alojamiento por noche; los pagos no equivalen a ingresos. Movimientos históricos pueden carecer de fecha.',
    }
