
"""Registro documental cifrado del check-in.

Revision ID: 6a17checkin
Revises: 5a12rooms
"""

from alembic import op
import sqlalchemy as sa


revision = "6a17checkin"
down_revision = "5a12rooms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "check_in_records",
        sa.Column(
            "reservation_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "encrypted_payload",
            sa.LargeBinary(),
            nullable=False,
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "guarantee_accepted",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "missing_guarantee_risk",
            sa.Boolean(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"],
            ["reservations.id"],
        ),
        sa.PrimaryKeyConstraint("reservation_id"),
    )


def downgrade() -> None:
    op.drop_table("check_in_records")
