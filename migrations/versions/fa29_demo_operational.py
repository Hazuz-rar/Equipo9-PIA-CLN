"""Catálogos y escenarios ficticios del profesor en el PMS.

Revision ID: fa29demo
Revises: ea28walk
"""
from alembic import op
import sqlalchemy as sa

revision = "fa29demo"
down_revision = "ea28walk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_guests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_actor_id", sa.String(20), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "demo_scenarios",
        sa.Column("operation_id", sa.String(20), primary_key=True),
        sa.Column("guest_id", sa.Uuid(), sa.ForeignKey("demo_guests.id"), nullable=False),
        sa.Column("requested_at", sa.Date(), nullable=False),
        sa.Column("initial_state", sa.String(30), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("authorized", sa.Boolean(), nullable=False),
        sa.Column("promotion_active", sa.Boolean(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("example_total_mxn", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "demo_scenario_lines",
        sa.Column("operation_id", sa.String(20), sa.ForeignKey("demo_scenarios.operation_id"), primary_key=True),
        sa.Column("source_resource_id", sa.String(20), primary_key=True),
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_mxn", sa.Numeric(12, 2), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("demo_scenario_lines")
    op.drop_table("demo_scenarios")
    op.drop_table("demo_guests")
