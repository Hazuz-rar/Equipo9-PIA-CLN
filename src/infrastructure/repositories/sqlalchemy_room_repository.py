"""Repositorio de Habitaciones; consulta de disponibilidad centralizada.

El estado de ocupación es operativo; se requieren más datos para distinguir
limpia/sucia/inspeccionada y para la sincronización con OTAs (RF-07, US-25).
"""
from uuid import UUID

from sqlalchemy import exists, func, select, and_, or_
from datetime import datetime, timezone
from src.infrastructure.database.models.group_model import GroupBookingModel, GroupHeldRoomModel
from sqlalchemy.orm import Session

from src.application.rooms.queries import AvailableRoom
from src.application.rooms.operations import PendingCleaningRoom
from src.domain.reservations.entities import ReservationStatus
from src.domain.reservations.value_objects import RoomId, StayPeriod
from src.domain.rooms.entities import Room, RoomStatus
from src.domain.rooms.value_objects import Capacity, Money, RoomNumber
from src.infrastructure.database.models.reservation_model import ReservationModel
from src.infrastructure.database.models.room_model import RoomModel


class SQLAlchemyRoomRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, room_id: UUID, room: Room) -> None:
        self.session.add(
            RoomModel(
                id=room_id,
                number=room.number.value,
                room_type=room.room_type,
                capacity=room.capacity.value,
                base_rate=room.base_rate.amount,
                status=room.status,
            )
        )
        self.session.flush()

    def get_by_id(self, room_id: RoomId) -> Room | None:
        row = self.session.get(RoomModel, room_id.value)
        if row is None:
            return None
        return Room(
            number=RoomNumber(row.number),
            room_type=row.room_type,
            capacity=Capacity(row.capacity),
            base_rate=Money(row.base_rate),
            status=row.status,
        )

    def get_for_update(self, room_id: RoomId) -> Room | None:
        row = self.session.scalar(
            select(RoomModel)
            .where(RoomModel.id == room_id.value)
            .with_for_update()
        )
        if row is None:
            return None
        return Room(
            number=RoomNumber(row.number),
            room_type=row.room_type,
            capacity=Capacity(row.capacity),
            base_rate=Money(row.base_rate),
            status=row.status,
        )

    def update(self, room_id: RoomId, room: Room) -> None:
        row = self.session.get(RoomModel, room_id.value)
        if row is None:
            raise ValueError("La habitación no existe en el inventario.")
        row.status = room.status
        self.session.flush()

    def list_dirty(self) -> list[PendingCleaningRoom]:
        """US-14: consultar habitaciones pendientes de limpieza."""
        rows = self.session.scalars(
            select(RoomModel)
            .where(RoomModel.status == RoomStatus.DIRTY)
            .order_by(RoomModel.number)
        )
        return [
            PendingCleaningRoom(
                id=row.id,
                number=row.number,
                room_type=row.room_type,
            )
            for row in rows
        ]

    def find_available(
        self,
        period: StayPeriod,
        room_type: str | None,
        guests: int,
    ) -> list[AvailableRoom]:
        clashes = (
            select(ReservationModel.id)
            .where(
                ReservationModel.room_id == RoomModel.id,
                ReservationModel.status.in_(
                    [ReservationStatus.CONFIRMED, ReservationStatus.CHECK_IN]
                ),
                ReservationModel.check_in < period.check_out,
                ReservationModel.check_out > period.check_in,
            )
            .correlate(RoomModel)
            .exists()
        )
        group_clashes = (
            select(GroupHeldRoomModel.room_id)
            .join(GroupBookingModel, GroupBookingModel.id == GroupHeldRoomModel.group_id)
            .where(
                GroupHeldRoomModel.room_id == RoomModel.id,
                GroupBookingModel.check_in < period.check_out,
                GroupBookingModel.check_out > period.check_in,
                or_(
                    GroupBookingModel.status == 'CONFIRMED',
                    and_(GroupBookingModel.status == 'PENDING_DEPOSIT',
                         GroupBookingModel.deposit_due_at > datetime.now(timezone.utc)),
                ),
            )
            .correlate(RoomModel).exists()
        )
        statement = select(RoomModel).where(
            RoomModel.status.in_((RoomStatus.AVAILABLE, RoomStatus.INSPECTED)),
            ~group_clashes,
            RoomModel.capacity >= guests,
            ~clashes,
        )
        if room_type is not None:
            statement = statement.where(
                func.lower(RoomModel.room_type) == room_type.lower()
            )
        statement = statement.order_by(RoomModel.number)
        return [
            AvailableRoom(
                id=row.id,
                number=row.number,
                room_type=row.room_type,
                capacity=row.capacity,
                base_rate=row.base_rate,
                currency="MXN",  # Limitación actual del Value Object Money.
            )
            for row in self.session.scalars(statement)
        ]
