"""Catálogos y escenarios FICTICIOS del profesor; no son reservas confirmadas."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class DemoGuestModel(Base):
    __tablename__ = "demo_guests"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_actor_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class DemoScenarioModel(Base):
    __tablename__ = "demo_scenarios"

    operation_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    guest_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("demo_guests.id"), nullable=False
    )
    requested_at: Mapped[date] = mapped_column(Date, nullable=False)
    initial_state: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    promotion_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    example_total_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class DemoScenarioLineModel(Base):
    __tablename__ = "demo_scenario_lines"

    operation_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("demo_scenarios.operation_id"), primary_key=True
    )
    source_resource_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    room_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("rooms.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_mxn: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
