"""Registro de excepciones y salida de eventos; sin integración real de pagos u OTAs."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Uuid, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base

class ReservationGuaranteeModel(Base):
    __tablename__='reservation_guarantees'
    reservation_id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('reservations.id'),primary_key=True)
    method: Mapped[str]=mapped_column(String(80),nullable=False)
    external_reference: Mapped[str]=mapped_column(String(255),nullable=False)
    verified_by: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('staff_users.id'),nullable=False)
    recorded_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)

class ReservationFinancialEventModel(Base):
    __tablename__='reservation_financial_events'
    id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
    reservation_id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('reservations.id'),nullable=False,index=True)
    event_type: Mapped[str]=mapped_column(String(60),nullable=False)
    amount: Mapped[Decimal]=mapped_column(Numeric(12,2),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),nullable=False)
    settlement_status: Mapped[str]=mapped_column(String(40),nullable=False)
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    actor_id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('staff_users.id'),nullable=False)

class AvailabilityOutboxModel(Base):
    __tablename__='availability_outbox'
    id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),primary_key=True,default=uuid4)
    reservation_id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True),ForeignKey('reservations.id'),nullable=False,index=True)
    action: Mapped[str]=mapped_column(String(50),nullable=False)
    payload: Mapped[dict]=mapped_column(JSON,nullable=False)
    published: Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    published_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)
