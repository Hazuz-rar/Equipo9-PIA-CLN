"""Operaciones autenticadas para la futura interfaz gráfica.

ADR-004: los cambios de estancia se ejecutan en Unit of Work.
Estas rutas no admiten suplantar actor mediante datos del cliente.
"""
from datetime import datetime, date, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.core.config import settings
from src.core.security import StaffIdentity, require_roles
from src.domain.reception.check_in import GuestCheckInRegistration
from src.application.reception.services import CheckInRegistrationService
from src.application.reception.operations import OperationalCheckInService, OperationalCheckOutService
from src.infrastructure.check_in_unit_of_work import SQLAlchemyCheckInUnitOfWork
from src.infrastructure.room_cleaning_unit_of_work import SQLAlchemyRoomCleaningUnitOfWork
from src.infrastructure.repositories.sqlalchemy_reservation_repository import SQLAlchemyReservationRepository
from src.infrastructure.repositories.sqlalchemy_check_in_repository import SQLAlchemyCheckInRepository
from src.infrastructure.repositories.sqlalchemy_folio_repository import SQLAlchemyFolioRepository
from src.application.rooms.operations import HousekeepingService, HotelStaffRole
from src.domain.folios.value_objects import ChargeAmount, PaymentAmount, FolioId
from src.domain.folios.vouchers import ChargeVoucher
from src.infrastructure.database.models.staff_model import BusinessAuditModel
from src.infrastructure.database.session import SessionLocal

router = APIRouter()

RECEPTION_ROLES = ('RECEPTION','MANAGER_RECEPTION','MANAGER_OPERATIONS')
FINANCE_ROLES = ('RECEPTION','FINANCE','MANAGER_RECEPTION','MANAGER_OPERATIONS')


def hotel_zone():
    if not settings.hotel_timezone:
        raise HTTPException(status_code=503, detail='Configura HOTEL_TIMEZONE (zona IANA del hotel).')
    try:
        return ZoneInfo(settings.hotel_timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=503, detail='HOTEL_TIMEZONE no es válida.') from exc


def fernet_key():
    if not settings.checkin_data_key:
        raise HTTPException(status_code=503, detail='Falta CHECKIN_DATA_KEY.')
    return settings.checkin_data_key


def record_audit(session: Session, actor: StaffIdentity, action: str, entity_type: str, entity_id: UUID, details: dict | None = None):
    session.add(BusinessAuditModel(
        actor_id=actor.id, action=action, entity_type=entity_type,
        entity_id=entity_id, details=details or {},
        occurred_at=datetime.now(timezone.utc),
    ))


class CheckInDocumentRequest(BaseModel):
    full_name: str = Field(min_length=1)
    official_id_number: str = Field(min_length=1)
    official_id_valid_until: date
    nationality: str = Field(min_length=1)
    contact_details: str = Field(min_length=1)
    invoice_requested: bool = False
    fiscal_address: str | None = None
    guarantee_accepted: bool


class OperationTime(BaseModel):
    # Un horario simulado únicamente se admite en el entorno local de desarrollo.
    simulated_at: datetime | None = None


def operational_time(data: OperationTime):
    if data.simulated_at is None:
        return datetime.now(timezone.utc)
    if settings.app_env != 'development':
        raise HTTPException(status_code=403, detail='No se admite hora simulada fuera de desarrollo.')
    if data.simulated_at.tzinfo is None or data.simulated_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail='La hora simulada necesita zona horaria.')
    return data.simulated_at


@router.post('/reservations/{reservation_id}/check-in-documentation')
def register_documentation(
    reservation_id: UUID, data: CheckInDocumentRequest,
    actor: StaffIdentity = Depends(require_roles(*RECEPTION_ROLES)),
    session: Session = Depends(get_db),
):
    key = fernet_key()
    now = datetime.now(timezone.utc)
    try:
        record = GuestCheckInRegistration(**data.model_dump(), registered_at=now)
        service = CheckInRegistrationService(
            SQLAlchemyReservationRepository(session),
            SQLAlchemyCheckInRepository(session, key),
        )
        missing = service.register(reservation_id, record)
        record_audit(session, actor, 'CHECKIN_DOCUMENTATION_REGISTERED', 'reservation', reservation_id,
                     {'missing_guarantee_risk': missing})
        session.commit()
        return {'reservation_id': reservation_id, 'missing_guarantee_risk': missing}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise


@router.post('/reservations/{reservation_id}/check-in')
def check_in(
    reservation_id: UUID, data: OperationTime,
    actor: StaffIdentity = Depends(require_roles(*RECEPTION_ROLES)),
):
    zone = hotel_zone()
    key = fernet_key()
    try:
        result = OperationalCheckInService(
            lambda: SQLAlchemyCheckInUnitOfWork(SessionLocal, key, actor.id, "CHECK_IN", reservation_id), zone,
            allow_early_if_clean=True,
        ).execute(reservation_id, operational_time(data))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@router.post('/reservations/{reservation_id}/check-out')
def check_out(
    reservation_id: UUID, data: OperationTime,
    actor: StaffIdentity = Depends(require_roles(*RECEPTION_ROLES)),
):
    zone = hotel_zone()
    try:
        result = OperationalCheckOutService(
            lambda: SQLAlchemyCheckInUnitOfWork(SessionLocal, fernet_key(), actor.id, "CHECK_OUT", reservation_id), zone,
        ).execute(reservation_id, operational_time(data))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@router.get('/rooms/dirty')
def pending_cleaning(actor: StaffIdentity = Depends(require_roles('HOUSEKEEPING'))):
    service = HousekeepingService(lambda: SQLAlchemyRoomCleaningUnitOfWork(SessionLocal))
    return service.list_pending(HotelStaffRole.HOUSEKEEPING)


@router.post('/rooms/{room_id}/clean')
def finish_cleaning(room_id: UUID, actor: StaffIdentity = Depends(require_roles('HOUSEKEEPING'))):
    service = HousekeepingService(lambda: SQLAlchemyRoomCleaningUnitOfWork(SessionLocal))
    try:
        status = service.finish_cleaning(room_id, actor.id, HotelStaffRole.HOUSEKEEPING)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {'room_id':room_id,'status':status.value}


class VoucherRequest(BaseModel):
    room_number: str = Field(min_length=1, max_length=30)
    guest_name: str = Field(min_length=1, max_length=200)
    guest_signature: str = Field(min_length=1, max_length=500)
    issued_at: datetime
    point_of_sale: str = Field(min_length=1, max_length=100)
    consumption_detail: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0)
    voucher_number: str = Field(min_length=1, max_length=100)


class PaymentRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0)


def locked_folio(session, folio_id):
    repo = SQLAlchemyFolioRepository(session)
    # Esta lectura se hace con lock de fila de folio, no solo del objeto de dominio.
    from sqlalchemy import select
    from src.infrastructure.database.models.folio_model import FolioModel
    model = session.scalar(select(FolioModel).where(FolioModel.id == folio_id).with_for_update())
    if model is None:
        raise HTTPException(status_code=404, detail='El folio no existe.')
    folio = repo.get_by_id(FolioId(folio_id))
    return repo, folio


@router.post('/folios/{folio_id}/charges', status_code=201)
def post_charge(
    folio_id: UUID, data: VoucherRequest,
    actor: StaffIdentity = Depends(require_roles(*FINANCE_ROLES)),
    session: Session = Depends(get_db),
):
    try:
        repo, folio = locked_folio(session, folio_id)
        voucher = ChargeVoucher(**data.model_dump())
        # Se comprueba que el vale corresponde a la habitación registrada del huésped.
        from src.infrastructure.database.models.reservation_model import ReservationModel
        from src.infrastructure.database.models.room_model import RoomModel
        reservation = session.get(ReservationModel, folio.reservation_id.value)
        room = session.get(RoomModel, reservation.room_id) if reservation else None
        if room is None or voucher.room_number != room.number:
            raise ValueError('El vale no corresponde a la habitación del folio.')
        folio.add_voucher_charge(voucher)
        repo.update(folio)
        record_audit(session, actor, 'FOLIO_CHARGE', 'folio', folio_id,
                     {'voucher_number': voucher.voucher_number, 'amount':str(voucher.amount)})
        session.commit()
        return {'folio_id': folio_id, 'balance':str(folio.balance)}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise


@router.post('/folios/{folio_id}/payments', status_code=201)
def post_payment(
    folio_id: UUID, data: PaymentRequest,
    actor: StaffIdentity = Depends(require_roles(*FINANCE_ROLES)),
    session: Session = Depends(get_db),
):
    try:
        repo, folio = locked_folio(session, folio_id)
        folio.add_payment(data.description, PaymentAmount(data.amount))
        repo.update(folio)
        record_audit(session, actor, 'FOLIO_PAYMENT', 'folio', folio_id,
                     {'amount':str(data.amount)})
        session.commit()
        return {'folio_id': folio_id, 'balance':str(folio.balance)}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

class IncidentRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class RestoreRoomRequest(BaseModel):
    requires_cleaning: bool = True


@router.post('/rooms/{room_id}/out-of-service', status_code=201)
def report_incident(
    room_id: UUID, data: IncidentRequest,
    actor: StaffIdentity = Depends(require_roles('RECEPTION', 'MAINTENANCE', 'MANAGER_RECEPTION', 'MANAGER_OPERATIONS')),
    session: Session = Depends(get_db),
):
    from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
    from src.domain.reservations.value_objects import RoomId
    from src.infrastructure.database.models.staff_model import RoomIncidentModel
    from src.domain.rooms.entities import RoomStatus
    from sqlalchemy import select
    try:
        repo = SQLAlchemyRoomRepository(session)
        room = repo.get_for_update(RoomId(room_id))
        if room is None:
            raise HTTPException(status_code=404, detail='La habitación no existe.')
        if room.status == RoomStatus.OUT_OF_ORDER:
            raise ValueError('La habitación ya está fuera de servicio.')
        room.mark_out_of_order()
        repo.update(RoomId(room_id), room)
        incident = RoomIncidentModel(room_id=room_id, reason=data.reason.strip(), reported_by=actor.id, reported_at=datetime.now(timezone.utc))
        session.add(incident)
        session.flush()
        record_audit(session, actor, 'ROOM_OUT_OF_ORDER', 'room', room_id, {'incident_id':str(incident.id),'reason':data.reason.strip()})
        session.commit()
        return {'incident_id':incident.id,'room_id':room_id,'status':room.status.value}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise


@router.post('/incidents/{incident_id}/resolve')
def resolve_incident(
    incident_id: UUID,
    actor: StaffIdentity = Depends(require_roles('MAINTENANCE')),
    session: Session = Depends(get_db),
):
    from src.infrastructure.database.models.staff_model import RoomIncidentModel
    from sqlalchemy import select
    try:
        incident = session.scalar(select(RoomIncidentModel).where(RoomIncidentModel.id == incident_id).with_for_update())
        if incident is None:
            raise HTTPException(status_code=404, detail='Incidencia inexistente.')
        if incident.resolved_at is not None:
            raise ValueError('La incidencia ya fue resuelta.')
        incident.resolved_by = actor.id
        incident.resolved_at = datetime.now(timezone.utc)
        record_audit(session, actor, 'ROOM_INCIDENT_RESOLVED', 'room', incident.room_id, {'incident_id':str(incident.id)})
        session.commit()
        return {'incident_id':incident_id,'resolved':True}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise


@router.post('/rooms/{room_id}/restore')
def restore_room(
    room_id: UUID, data: RestoreRoomRequest,
    actor: StaffIdentity = Depends(require_roles('MANAGER_RECEPTION', 'MANAGER_OPERATIONS')),
    session: Session = Depends(get_db),
):
    from sqlalchemy import select
    from src.infrastructure.database.models.staff_model import RoomIncidentModel
    from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
    from src.domain.reservations.value_objects import RoomId
    try:
        repo = SQLAlchemyRoomRepository(session)
        room = repo.get_for_update(RoomId(room_id))
        if room is None:
            raise HTTPException(status_code=404, detail='La habitación no existe.')
        incident = session.scalar(select(RoomIncidentModel)
                                  .where(RoomIncidentModel.room_id == room_id, RoomIncidentModel.restored_at.is_(None))
                                  .order_by(RoomIncidentModel.reported_at.desc()).with_for_update())
        if incident is None or incident.resolved_at is None:
            raise ValueError('Mantenimiento debe confirmar la resolución antes de reactivar.')
        room.restore_after_maintenance(data.requires_cleaning)
        repo.update(RoomId(room_id), room)
        incident.restored_by = actor.id
        incident.restored_at = datetime.now(timezone.utc)
        record_audit(session, actor, 'ROOM_RESTORED', 'room', room_id,
                     {'incident_id':str(incident.id),'requires_cleaning':data.requires_cleaning})
        session.commit()
        return {'room_id':room_id, 'status':room.status.value}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise


@router.get('/audit')
def list_audit(
    limit: int = 100,
    actor: StaffIdentity = Depends(require_roles('FINANCE', 'MANAGER_RECEPTION', 'MANAGER_OPERATIONS')),
    session: Session = Depends(get_db),
):
    from sqlalchemy import select
    from fastapi import Query
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail='Límite permitido: 1 a 200.')
    rows = session.scalars(select(BusinessAuditModel).order_by(BusinessAuditModel.occurred_at.desc()).limit(limit)).all()
    return [{'id':r.id,'actor_id':r.actor_id,'action':r.action,'entity_type':r.entity_type,
             'entity_id':r.entity_id,'details':r.details,'occurred_at':r.occurred_at} for r in rows]

@router.get('/folios/{folio_id}')
def read_folio_for_staff(
    folio_id:UUID,
    actor:StaffIdentity=Depends(require_roles(*FINANCE_ROLES)),
    session:Session=Depends(get_db),
):
    from src.api.schemas.folio import FolioResponse
    repo=SQLAlchemyFolioRepository(session)
    folio=repo.get_by_id(FolioId(folio_id))
    if folio is None:
        raise HTTPException(status_code=404,detail='El folio no existe.')
    return FolioResponse.from_domain(folio)

@router.post('/reservations/{reservation_id}/late-checkout-charge')
def apply_late_checkout_charge(
    reservation_id:UUID,data:OperationTime,
    actor:StaffIdentity=Depends(require_roles(*RECEPTION_ROLES)),
    session:Session=Depends(get_db),
):
    from sqlalchemy import select
    from src.domain.reservations.entities import ReservationStatus
    from src.domain.reservations.late_checkout import late_checkout_charge
    from src.infrastructure.database.models.reservation_model import ReservationModel
    from src.infrastructure.database.models.tariff_model import ReservationQuoteModel
    from src.domain.folios.value_objects import ChargeAmount
    from datetime import time
    try:
        zone=hotel_zone()
        when=operational_time(data).astimezone(zone)
        reservation=session.scalar(select(ReservationModel).where(ReservationModel.id==reservation_id).with_for_update())
        if reservation is None:
            raise HTTPException(status_code=404,detail='La reserva no existe.')
        if reservation.status!=ReservationStatus.CHECK_IN or when.date()!=reservation.check_out:
            raise ValueError('El cargo de late check-out requiere una estancia en su día de salida.')
        terms=session.get(ReservationQuoteModel,reservation_id)
        if terms is None or not terms.nightly_breakdown:
            raise ValueError('No existe tarifa aceptada para calcular late check-out.')
        amount=late_checkout_charge(when.time(),Decimal(terms.nightly_breakdown[-1]['amount']))
        if amount==0:
            return {'reservation_id':reservation_id,'amount':amount,'message':'Salida dentro de tolerancia; sin cargo.'}
        repo=SQLAlchemyFolioRepository(session)
        folio=repo.get_by_reservation_id_for_update(reservation_id)
        if folio is None:
            raise ValueError('No existe folio abierto.')
        if any(c.description=='Late check-out RN-03' for c in folio.charges):
            raise ValueError('El cargo de late check-out ya está registrado.')
        folio.add_charge('Late check-out RN-03',ChargeAmount(amount))
        repo.update(folio)
        record_audit(session,actor,'LATE_CHECKOUT_CHARGE','folio',folio.id.value,
                     {'reservation_id':str(reservation_id),'amount':str(amount)})
        session.commit()
        return {'reservation_id':reservation_id,'folio_id':folio.id.value,'amount':amount,
                'balance':folio.balance,'currency':terms.currency}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

@router.post('/rooms/{room_id}/inspect')
def inspect_room(
    room_id:UUID,
    actor:StaffIdentity=Depends(require_roles('HOUSEKEEPING','MANAGER_RECEPTION','MANAGER_OPERATIONS')),
    session:Session=Depends(get_db),
):
    """RF-07: registrar revisión de una habitación ya marcada como limpia."""
    from src.infrastructure.repositories.sqlalchemy_room_repository import SQLAlchemyRoomRepository
    from src.domain.reservations.value_objects import RoomId
    try:
        repo=SQLAlchemyRoomRepository(session)
        room=repo.get_for_update(RoomId(room_id))
        if room is None:
            raise HTTPException(status_code=404,detail='Habitación inexistente.')
        room.mark_inspected()
        repo.update(RoomId(room_id),room)
        record_audit(session,actor,'ROOM_INSPECTED','room',room_id)
        session.commit()
        return {'room_id':room_id,'status':room.status.value}
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise
