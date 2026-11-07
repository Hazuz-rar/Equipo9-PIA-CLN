
"""Crear catálogo de habitaciones.

Revision ID: 5a12rooms
Revises: 4a11csv
"""

from alembic import op
import sqlalchemy as sa


revision = "5a12rooms"
down_revision = "4a11csv"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "rooms",

        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),

        sa.Column(
            "number",
            sa.String(10),
            nullable=False,
        ),

        sa.Column(
            "room_type",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "capacity",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "base_rate",
            sa.Numeric(12, 2),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.Enum(
                "AVAILABLE",
                "OCCUPIED",
                "OUT_OF_ORDER",
                native_enum=False,
            ),
            nullable=False,
        ),

        sa.CheckConstraint(
            "capacity > 0",
            name="ck_room_capacity_positive",
        ),

        sa.CheckConstraint(
            "base_rate >= 0",
            name="ck_room_rate_nonnegative",
        ),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )


def downgrade() -> None:
    op.drop_table("rooms")
