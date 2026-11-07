"""Bloqueos de diez o más habitaciones para US-22."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base

class GroupBookingModel(Base):
    __tablename__='group_bookings'
    id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
    organizer:Mapped[str]=mapped_column(String(150),nullable=False)
    contract_reference:Mapped[str]=mapped_column(String(150),nullable=False)
    check_in:Mapped[date]=mapped_column(Date(),nullable=False)
    check_out:Mapped[date]=mapped_column(Date(),nullable=False)
    deposit_due_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    total:Mapped[Decimal]=mapped_column(Numeric(12,2),nullable=False)
    currency:Mapped[str]=mapped_column(String(3),nullable=False)
    required_deposit:Mapped[Decimal]=mapped_column(Numeric(12,2),nullable=False)
    deposit_paid:Mapped[Decimal]=mapped_column(Numeric(12,2),nullable=False,default=0)
    deposit_reference:Mapped[str | None]=mapped_column(String(150),nullable=True)
    status:Mapped[str]=mapped_column(String(32),nullable=False)
    created_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('staff_users.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)

class GroupHeldRoomModel(Base):
    __tablename__='group_held_rooms'
    group_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('group_bookings.id'),primary_key=True)
    room_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('rooms.id'),primary_key=True)
