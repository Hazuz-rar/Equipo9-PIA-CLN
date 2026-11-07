"""Repositorio SQLAlchemy para Reserva, con bloqueo por habitación.

En PostgreSQL pg_advisory_xact_lock serializa confirmaciones de la misma
habitación; se libera automáticamente al COMMIT/ROLLBACK. En SQLite
solo se prueba el flujo secuencial: no ofrece la misma protección.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.application.ports.reservation_repository import ReservationRepository
from src.domain.reservations.entities import Reservation, ReservationStatus
from src.domain.reservations.value_objects import (
    GuestId,
    ReservationId,
    RoomId,
    StayPeriod,
)
from src.infrastructure.database.models.reservation_model import ReservationModel


class SQLAlchemyReservationRepository(ReservationRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, reservation: Reservation) -> None:
        model = ReservationModel(
            id=reservation.id.value,
            guest_id=reservation.guest_id.value,
            room_id=reservation.room_id.value,
            check_in=reservation.stay_period.check_in,
            check_out=reservation.stay_period.check_out,
            status=reservation.status,
        )
        self.session.add(model)
        self.session.flush()

    def get_by_id(self, reservation_id: ReservationId) -> Reservation | None:
        statement = select(ReservationModel).where(
            ReservationModel.id == reservation_id.value
        )
        model = self.session.scalar(statement)
        return None if model is None else self._to_entity(model)

    def get_for_update(self, reservation_id: ReservationId) -> Reservation | None:
        statement = (select(ReservationModel)
                     .where(ReservationModel.id == reservation_id.value)
                     .with_for_update())
        model = self.session.scalar(statement)
        return self._to_entity(model) if model is not None else None

    def lock_room(self, room_id: RoomId) -> None:
        if self.session.get_bind().dialect.name != "postgresql":
            return  # SQLite en pruebas: sin garantía para confirmaciones concurrentes
        key = room_id.value.int & ((1 << 64) - 1)
        if key >= (1 << 63):
            key -= 1 << 64
        self.session.execute(select(func.pg_advisory_xact_lock(key)))

    def find_active_by_room_and_period(
        self,
        room_id: RoomId,
        stay_period: StayPeriod,
        exclude_id: ReservationId,
    ) -> list[Reservation]:
        statement = select(ReservationModel).where(
            ReservationModel.room_id == room_id.value,
            ReservationModel.id != exclude_id.value,
            ReservationModel.status.in_(
                [ReservationStatus.CONFIRMED, ReservationStatus.CHECK_IN]
            ),
            ReservationModel.check_in < stay_period.check_out,
            ReservationModel.check_out > stay_period.check_in,
        )
        return [self._to_entity(row) for row in self.session.scalars(statement)]

    def update(self, reservation: Reservation) -> None:
        model = self.session.get(ReservationModel, reservation.id.value)
        if model is None:
            raise ValueError("La reserva no existe en la base de datos.")
        model.guest_id = reservation.guest_id.value
        model.room_id = reservation.room_id.value
        model.check_in = reservation.stay_period.check_in
        model.check_out = reservation.stay_period.check_out
        model.status = reservation.status
        self.session.flush()

    @staticmethod
    def _to_entity(model: ReservationModel) -> Reservation:
        return Reservation(
            id=ReservationId(model.id),
            guest_id=GuestId(model.guest_id),
            room_id=RoomId(model.room_id),
            stay_period=StayPeriod(
                check_in=model.check_in,
                check_out=model.check_out,
            ),
            status=model.status,
        )
