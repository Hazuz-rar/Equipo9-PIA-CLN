"""RN-06 / US-23: expediente de reubicación y evidencia manual de hotel aliado."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base

class WalkCaseModel(Base):
    __tablename__='walk_cases'
    id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
    reservation_id:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('reservations.id'),nullable=False,unique=True)
    allied_hotel:Mapped[str]=mapped_column(String(150),nullable=False)
    transport_details:Mapped[str]=mapped_column(String(500),nullable=False)
    fare_difference:Mapped[Decimal]=mapped_column(Numeric(12,2),nullable=False)
    courtesy_details:Mapped[str]=mapped_column(String(500),nullable=False)
    partner_booking_reference:Mapped[str | None]=mapped_column(String(200),nullable=True)
    state:Mapped[str]=mapped_column(String(50),nullable=False)
    approved_by:Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('staff_users.id'),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    confirmed_at:Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
