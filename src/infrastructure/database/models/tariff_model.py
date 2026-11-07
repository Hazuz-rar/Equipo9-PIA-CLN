"""Configuración de tarifas aprobada por gerencia; los valores no están predefinidos."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base

class TariffConfigurationModel(Base):
    __tablename__ = 'tariff_configurations'
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    authorized_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('staff_users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc), nullable=False)

class ReservationQuoteModel(Base):
    __tablename__ = 'reservation_quotes'
    reservation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('reservations.id'), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(40), nullable=False)
    first_night: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    nightly_breakdown: Mapped[list] = mapped_column(JSON, nullable=False)
    guest_accepted: Mapped[bool] = mapped_column(nullable=False)
    authorized_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('staff_users.id'), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
