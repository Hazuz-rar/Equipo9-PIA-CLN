"""Auditoría de limpieza: US-14, US-15, RNF-01 parcial.

Revision ID: 7a21clean
Revises: 6a17checkin
"""

from alembic import op
import sqlalchemy as sa

revision = "7a21clean"
down_revision = "6a17checkin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "room_cleaning_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_role", sa.String(length=40), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=False),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_room_cleaning_events_room_id",
        "room_cleaning_events", ["room_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_room_cleaning_events_room_id", table_name="room_cleaning_events")
    op.drop_table("room_cleaning_events")
