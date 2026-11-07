"""Reubicación por sobreventa (walk).
Revision ID: ea28walk
Revises: da27groups
"""
from alembic import op
import sqlalchemy as sa
revision='ea28walk'
down_revision='da27groups'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name=='postgresql':
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE reservation_status ADD VALUE IF NOT EXISTS 'RELOCATED'")
    op.create_table('walk_cases',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('reservation_id',sa.Uuid(),sa.ForeignKey('reservations.id'),nullable=False,unique=True),
        sa.Column('allied_hotel',sa.String(150),nullable=False),
        sa.Column('transport_details',sa.String(500),nullable=False),
        sa.Column('fare_difference',sa.Numeric(12,2),nullable=False),
        sa.Column('courtesy_details',sa.String(500),nullable=False),
        sa.Column('partner_booking_reference',sa.String(200),nullable=True),
        sa.Column('state',sa.String(50),nullable=False),
        sa.Column('approved_by',sa.Uuid(),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('confirmed_at',sa.DateTime(timezone=True),nullable=True),
    )

def downgrade():
    op.drop_table('walk_cases')
    # El ENUM de PostgreSQL conserva RELOCATED por seguridad.
