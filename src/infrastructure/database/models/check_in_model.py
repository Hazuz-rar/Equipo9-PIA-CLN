
"""Datos de registro cifrados: no guardar identificación en texto plano."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class CheckInRecordModel(Base):
    __tablename__ = "check_in_records"

    reservation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reservations.id"),
        primary_key=True,
    )

    encrypted_payload: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    guarantee_accepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    missing_guarantee_risk: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
