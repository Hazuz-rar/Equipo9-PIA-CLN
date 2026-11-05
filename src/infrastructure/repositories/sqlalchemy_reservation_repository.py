
"""Repositorio de reservas con SQLAlchemy.

En PostgreSQL utiliza un bloqueo transaccional por habitación.
SQLite se utiliza únicamente para pruebas secuenciales.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.application.ports.reservation_repository import (
    ReservationRepository,
)
from src.domain.reservations.entities import (
    Reservation,
    ReservationStatus,
)
from src.domain.reservations.value_objects import (
    GuestId,
    ReservationId,
    RoomId,
    StayPeriod,
)
from src.infrastructure.database.models.reservation_model import (
    ReservationModel,
)


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

    def get_by_id(
        self,
        reservation_id: ReservationId,
    ) -> Reservation | None:
        statement = select(ReservationModel).where(
            ReservationModel.id == reservation_id.value
        )

        model = self.session.scalar(statement)

        if model is None:
            return None

        return self._to_entity(model)

    def lock_room(self, room_id: RoomId) -> None:
        if self.session.get_bind().dialect.name != "postgresql":
            return

        key = room_id.value.int & ((1 << 64) - 1)

        if key >= (1 << 63):
            key -= 1 << 64

        self.session.execute(
            select(func.pg_advisory_xact_lock(key))
        )

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
                [
                    ReservationStatus.CONFIRMED,
                    ReservationStatus.CHECK_IN,
                ]
            ),
            ReservationModel.check_in < stay_period.check_out,
            ReservationModel.check_out > stay_period.check_in,
        )

        return [
            self._to_entity(model)
            for model in self.session.scalars(statement)
        ]

    def update(self, reservation: Reservation) -> None:
        model = self.session.get(
            ReservationModel,
            reservation.id.value,
        )

        if model is None:
            raise ValueError(
                "La reserva no existe en la base de datos."
            )

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
