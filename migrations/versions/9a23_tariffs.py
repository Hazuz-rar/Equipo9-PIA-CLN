"""Parámetros de tarifas y cotización aceptada por reserva.

Revision ID: 9a23tariffs
Revises: 8a22security
"""
from alembic import op
import sqlalchemy as sa
revision='9a23tariffs'
down_revision='8a22security'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('tariff_configurations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('authorized_by',sa.Uuid(),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
    )
    op.create_table('reservation_quotes',
        sa.Column('reservation_id',sa.Uuid(),sa.ForeignKey('reservations.id'),primary_key=True),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('channel',sa.String(40),nullable=False),
        sa.Column('customer_type',sa.String(40),nullable=False),
        sa.Column('first_night',sa.Numeric(12,2),nullable=False),
        sa.Column('total',sa.Numeric(12,2),nullable=False),
        sa.Column('nightly_breakdown',sa.JSON(),nullable=False),
        sa.Column('guest_accepted',sa.Boolean(),nullable=False),
        sa.Column('authorized_by',sa.Uuid(),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('accepted_at',sa.DateTime(timezone=True),nullable=False),
    )

def downgrade():
    op.drop_table('reservation_quotes')
    op.drop_table('tariff_configurations')
