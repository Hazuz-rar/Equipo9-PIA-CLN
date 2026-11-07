
"""Persistencia de habitaciones del Hotel Costa Azul."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.rooms.entities import RoomStatus
from src.infrastructure.database.base import Base


class RoomModel(Base):
    __tablename__ = "rooms"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    number: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        unique=True,
    )

    room_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    base_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[RoomStatus] = mapped_column(
        Enum(
            RoomStatus,
            name="room_status",
            native_enum=False,
        ),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "capacity > 0",
            name="ck_room_capacity_positive",
        ),
        CheckConstraint(
            "base_rate >= 0",
            name="ck_room_rate_nonnegative",
        ),
    )
