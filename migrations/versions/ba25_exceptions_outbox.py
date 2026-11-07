"""Eventos de cancelación/no-show y sincronización pendiente.

Revision ID: ba25exceptions
Revises: 9a23tariffs
"""
from alembic import op
import sqlalchemy as sa
revision='ba25exceptions'
down_revision='9a23tariffs'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name == 'postgresql':
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE reservation_status ADD VALUE IF NOT EXISTS 'NO_SHOW'")
    op.create_table('reservation_guarantees',
        sa.Column('reservation_id',sa.Uuid(),sa.ForeignKey('reservations.id'),primary_key=True),
        sa.Column('method',sa.String(80),nullable=False),
        sa.Column('external_reference',sa.String(255),nullable=False),
        sa.Column('verified_by',sa.Uuid(),sa.ForeignKey('staff_users.id'),nullable=False),
        sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=False),
    )
    op.create_table('reservation_financial_events',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('reservation_id',sa.Uuid(),sa.ForeignKey('reservations.id'),nullable=False),
        sa.Column('event_type',sa.String(60),nullable=False),
        sa.Column('amount',sa.Numeric(12,2),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),
        sa.Column('settlement_status',sa.String(40),nullable=False),
        sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('staff_users.id'),nullable=False),
    )
    op.create_index('ix_reservation_financial_events_reservation_id','reservation_financial_events',['reservation_id'])
    op.create_table('availability_outbox',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('reservation_id',sa.Uuid(),sa.ForeignKey('reservations.id'),nullable=False),
        sa.Column('action',sa.String(50),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('published',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('published_at',sa.DateTime(timezone=True),nullable=True),
    )
    op.create_index('ix_availability_outbox_reservation_id','availability_outbox',['reservation_id'])

def downgrade():
    op.drop_index('ix_availability_outbox_reservation_id',table_name='availability_outbox')
    op.drop_table('availability_outbox')
    op.drop_index('ix_reservation_financial_events_reservation_id',table_name='reservation_financial_events')
    op.drop_table('reservation_financial_events')
    op.drop_table('reservation_guarantees')
    # PostgreSQL no permite eliminar valores de ENUM de forma segura;
    # NO_SHOW queda registrado si se revierte esta migración.
