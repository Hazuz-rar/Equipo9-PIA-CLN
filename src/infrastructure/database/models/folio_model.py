"""Persistencia de Folio y sus movimientos."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.folios.entities import FolioStatus
from src.infrastructure.database.base import Base


class FolioModel(Base):
    __tablename__ = "folios"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    reservation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reservations.id"), nullable=False, index=True
    )
    status: Mapped[FolioStatus] = mapped_column(
        Enum(FolioStatus, name="folio_status", native_enum=False), nullable=False
    )


class FolioChargeModel(Base):
    __tablename__ = "folio_charges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    folio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("folios.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)

    # NULL en movimientos históricos, fecha en nuevas operaciones.
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # NULL en los cargos históricos, obligatorio en los nuevos cargos con vale.
    voucher_room_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    voucher_guest_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    voucher_guest_signature: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voucher_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voucher_point_of_sale: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voucher_consumption_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    voucher_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(" + " AND ".join(
                f"{column} IS NULL" for column in (
                    "voucher_room_number", "voucher_guest_name", "voucher_guest_signature",
                    "voucher_issued_at", "voucher_point_of_sale",
                    "voucher_consumption_detail", "voucher_number",
                )
            ) + ") OR (" + " AND ".join(
                f"{column} IS NOT NULL" for column in (
                    "voucher_room_number", "voucher_guest_name", "voucher_guest_signature",
                    "voucher_issued_at", "voucher_point_of_sale",
                    "voucher_consumption_detail", "voucher_number",
                )
            ) + ")",
            name="ck_folio_charge_voucher_complete",
        ),
    )


class FolioPaymentModel(Base):
    __tablename__ = "folio_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    folio_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("folios.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
