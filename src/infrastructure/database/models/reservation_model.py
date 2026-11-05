from sqlalchemy import Date, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID as PyUUID

from src.infrastructure.database.base import Base
from src.domain.reservations.entities import ReservationStatus


class ReservationModel(Base):
    __tablename__ = "reservations"

    id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    guest_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    room_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    check_in: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )

    check_out: Mapped[Date] = mapped_column(
        Date,
        nullable=False,
    )

    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status"),
        nullable=False,
    )