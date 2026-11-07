"""Reservas grupales y bloqueo individual de inventario.
Revision ID: da27groups
Revises: ca26reporting
"""
from alembic import op
import sqlalchemy as sa
revision='da27groups'
down_revision='ca26reporting'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('group_bookings',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organizer',sa.String(150),nullable=False),
        sa.Column('contract_reference',sa.String(150),nullable=False),
        sa.Column('check_in',sa.Date(),nullable=False),
        sa.Column('check_out',sa.Date(),nullable=False),
        sa.Column('deposit_due_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('total',sa.Numeric(12,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('required_deposit',sa.Numeric(12,2),nullable=False),
        sa.Column('deposit_paid',sa.Numeric(12,2),nullable=False),
        sa.Column('deposit_reference',sa.String(150),nullable=True),
        sa.Column('status',sa.String(32),nullable=False),
        sa.Column('created_by',sa.Uuid(),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
    )
    op.create_table('group_held_rooms',
        sa.Column('group_id',sa.Uuid(),sa.ForeignKey('group_bookings.id'),primary_key=True),
        sa.Column('room_id',sa.Uuid(),sa.ForeignKey('rooms.id'),primary_key=True),
    )
    op.create_index('ix_group_held_rooms_room_id','group_held_rooms',['room_id'])

def downgrade():
    op.drop_index('ix_group_held_rooms_room_id',table_name='group_held_rooms')
    op.drop_table('group_held_rooms')
    op.drop_table('group_bookings')
