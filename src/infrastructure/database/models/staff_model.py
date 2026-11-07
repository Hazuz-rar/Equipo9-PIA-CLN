"""Cuentas del personal; nunca almacenar contraseñas en texto plano."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from src.infrastructure.database.base import Base

class StaffUserModel(Base):
    __tablename__ = 'staff_users'
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

class BusinessAuditModel(Base):
    __tablename__ = 'business_audit'
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('staff_users.id'), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc), nullable=False)

class RoomIncidentModel(Base):
    __tablename__ = 'room_incidents'
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    room_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('rooms.id'), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    reported_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('staff_users.id'), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda:datetime.now(timezone.utc))
    resolved_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('staff_users.id'), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restored_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('staff_users.id'), nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
