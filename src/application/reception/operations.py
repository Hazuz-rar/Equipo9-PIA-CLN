"""Check-in operativo transaccional (RN-01, RN-11, US-07, US-08, ADR-004).

No expone un endpoint: pendiente autenticación/autorización y configuración
oficial de zona horaria. Early check-in, limpieza y no-show siguen pendientes.
"""
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, time, tzinfo
from typing import Callable, Protocol
from uuid import UUID, uuid4

from src.application.ports.reservation_repository import ReservationRepository
from src.application.ports.room_repository import RoomRepository
from src.application.reception.services import CheckInRecordStore
from src.domain.folios.entities import Folio, FolioStatus
from src.domain.folios.value_objects import FolioId, ReservationReference
from src.domain.reservations.entities import ReservationStatus
from src.domain.reservations.value_objects import ReservationId


class FolioStore(Protocol):
    def get_by_reservation_id(self, reservation_id: UUID) -> Folio | None: ...
    def get_by_reservation_id_for_update(self, reservation_id: UUID) -> Folio | None: ...
    def add(self, folio: Folio) -> None: ...
    def update(self, folio: Folio) -> None: ...


class CheckInUnitOfWork(Protocol):
    reservations: ReservationRepository
    rooms: RoomRepository
    records: CheckInRecordStore
    folios: FolioStore

    def __enter__(self) -> "CheckInUnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


@dataclass(frozen=True)
class CheckInResult:
    reservation_id: UUID
    room_id: UUID
    folio_id: UUID


class OperationalCheckInService:
    def __init__(
        self,
        uow_factory: Callable[[], CheckInUnitOfWork],
        hotel_timezone: tzinfo,
        allow_early_if_clean: bool = False,
    ) -> None:
        self.allow_early_if_clean = allow_early_if_clean
        if hotel_timezone is None:
            raise ValueError("Se requiere la zona horaria del hotel.")
        self.uow_factory = uow_factory
        self.hotel_timezone = hotel_timezone

    def execute(self, reservation_id: UUID, performed_at: datetime) -> CheckInResult:
        # El horario es calculado en el servidor, no a partir de la hora del cliente.
        if not isinstance(performed_at, datetime) or (
            performed_at.tzinfo is None or performed_at.utcoffset() is None
        ):
            raise ValueError("Se requiere fecha y hora con zona horaria.")

        local_time = performed_at.astimezone(self.hotel_timezone)

        with self.uow_factory() as uow:
            reservation = uow.reservations.get_for_update(ReservationId(reservation_id))
            if reservation is None:
                raise ValueError("La reserva no existe.")
            if reservation.status != ReservationStatus.CONFIRMED:
                raise ValueError("Solo una reserva confirmada permite check-in.")
            if local_time.date() != reservation.stay_period.check_in:
                raise ValueError("El check-in estándar corresponde al día de llegada.")
            if local_time.time() < time(15, 0) and not self.allow_early_if_clean:
                raise ValueError("El early check-in requiere el control de limpieza RN-02.")

            registration = uow.records.get_by_reservation_id(reservation_id)
            if registration is None:
                raise ValueError("Falta la documentación obligatoria del huésped.")
            if registration.official_id_valid_until < local_time.date():
                raise ValueError("La identificación oficial está vencida.")
            if not registration.guarantee_accepted:
                # Se conserva la advertencia US-08, sin habilitar el folio.
                raise ValueError("Falta garantía válida; no se habilita el folio.")

            room = uow.rooms.get_for_update(reservation.room_id)
            if room is None:
                raise ValueError("La habitación no existe en el inventario.")
            if not room.can_accept_reservation():
                raise ValueError("La habitación no está disponible para check-in.")

            existing_folio = uow.folios.get_by_reservation_id(reservation_id)
            if existing_folio is not None and existing_folio.status != FolioStatus.OPEN:
                raise ValueError("La reserva tiene un folio cerrado.")

            reservation.check_in()
            room.mark_occupied()
            uow.reservations.update(reservation)
            uow.rooms.update(reservation.room_id, room)

            if existing_folio is None:
                existing_folio = Folio(
                    id=FolioId(uuid4()),
                    reservation_id=ReservationReference(reservation_id),
                )
                uow.folios.add(existing_folio)

            uow.commit()
            return CheckInResult(
                reservation_id=reservation_id,
                room_id=reservation.room_id.value,
                folio_id=existing_folio.id.value,
            )


@dataclass(frozen=True)
class CheckOutResult:
    reservation_id: UUID
    room_id: UUID
    folio_id: UUID


class OperationalCheckOutService:
    """US-09/US-13: salida ordinaria y habitación sucia, en una transacción.

    Salidas anticipadas o después de las 14:00 quedan BLOQUEADAS hasta
    implementar su cálculo financiero, evitando omitir cargos (US-09).
    Todavía NO genera automáticamente el cargo de hospedaje; valida el
    saldo del folio que efectivamente fue registrado por otros procesos.
    """

    def __init__(
        self,
        uow_factory: Callable[[], CheckInUnitOfWork],
        hotel_timezone: tzinfo,
    ) -> None:
        if hotel_timezone is None:
            raise ValueError("Se requiere la zona horaria del hotel.")
        self.uow_factory = uow_factory
        self.hotel_timezone = hotel_timezone

    def execute(self, reservation_id: UUID, performed_at: datetime) -> CheckOutResult:
        if not isinstance(performed_at, datetime) or (
            performed_at.tzinfo is None or performed_at.utcoffset() is None
        ):
            raise ValueError("Se requiere fecha y hora con zona horaria.")

        local_time = performed_at.astimezone(self.hotel_timezone)

        with self.uow_factory() as uow:
            reservation = uow.reservations.get_for_update(ReservationId(reservation_id))
            if reservation is None:
                raise ValueError("La reserva no existe.")
            if reservation.status != ReservationStatus.CHECK_IN:
                raise ValueError("Solo una estancia con check-in permite check-out.")

            if local_time.date() != reservation.stay_period.check_out:
                raise ValueError(
                    "La salida anticipada o en fecha distinta requiere revisión."
                )


            room = uow.rooms.get_for_update(reservation.room_id)
            if room is None:
                raise ValueError("La habitación no existe en el inventario.")

            folio = uow.folios.get_by_reservation_id_for_update(reservation_id)
            if folio is None:
                raise ValueError("La reserva no tiene folio registrado.")
            if folio.status != FolioStatus.OPEN:
                raise ValueError("El folio ya está cerrado.")
            if local_time.time() > time(14, 0):
                from src.domain.reservations.late_checkout import late_checkout_charge
                rate_reader = getattr(uow, 'last_night_rate', None)
                nightly_rate = rate_reader(reservation_id) if rate_reader else None
                if nightly_rate is None:
                    raise ValueError('El late check-out requiere tarifa y cargo RN-03.')
                required = late_checkout_charge(local_time.time(), nightly_rate)
                if not any(c.description == 'Late check-out RN-03' and c.amount.value == required
                           for c in folio.charges):
                    raise ValueError('El late check-out requiere registrar el cargo RN-03.')
            if folio.balance != Decimal("0.00"):
                raise ValueError("Debe liquidarse el saldo pendiente antes del check-out.")

            # Todas estas acciones comparten el COMMIT del UoW (ADR-004).
            # El dominio rechaza liberar una habitación que no esté OCUPADA.
            folio.close()
            reservation.check_out()
            room.mark_dirty()

            uow.folios.update(folio)
            uow.reservations.update(reservation)
            uow.rooms.update(reservation.room_id, room)
            uow.commit()

            return CheckOutResult(
                reservation_id=reservation_id,
                room_id=reservation.room_id.value,
                folio_id=folio.id.value,
            )
