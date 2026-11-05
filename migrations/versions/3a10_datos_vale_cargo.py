
"""Agregar datos del vale de cargos (RN-12).

Revision ID: 3a10voucher
Revises: 2a7folios
"""

from alembic import op
import sqlalchemy as sa


revision = "3a10voucher"
down_revision = "2a7folios"
branch_labels = None
depends_on = None


VOUCHER_FIELDS = (
    "voucher_room_number",
    "voucher_guest_name",
    "voucher_guest_signature",
    "voucher_issued_at",
    "voucher_point_of_sale",
    "voucher_consumption_detail",
    "voucher_number",
)


def upgrade() -> None:
    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_room_number",
            sa.String(30),
            nullable=True,
        ),
    )

    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_guest_name",
            sa.String(200),
            nullable=True,
        ),
    )

    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_guest_signature",
            sa.String(500),
            nullable=True,
        ),
    )

    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_issued_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_point_of_sale",
            sa.String(100),
            nullable=True,
        ),
    )

    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_consumption_detail",
            sa.String(500),
            nullable=True,
        ),
    )

    op.add_column(
        "folio_charges",
        sa.Column(
            "voucher_number",
            sa.String(100),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_folio_charge_voucher_complete",
        "folio_charges",
        "("
        + " AND ".join(
            f"{field} IS NULL"
            for field in VOUCHER_FIELDS
        )
        + ") OR ("
        + " AND ".join(
            f"{field} IS NOT NULL"
            for field in VOUCHER_FIELDS
        )
        + ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_folio_charge_voucher_complete",
        "folio_charges",
        type_="check",
    )

    for field in reversed(VOUCHER_FIELDS):
        op.drop_column(
            "folio_charges",
            field,
        )
