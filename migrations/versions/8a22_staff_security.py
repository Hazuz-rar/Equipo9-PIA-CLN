"""Cuentas de personal, auditoría e incidencias.

Revision ID: 8a22security
Revises: 7a21clean
"""
from alembic import op
import sqlalchemy as sa
revision = '8a22security'
down_revision = '7a21clean'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('staff_users',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('username', sa.String(80), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(40), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
    )
    op.create_table('business_audit',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('staff_users.id'), nullable=False),
        sa.Column('action', sa.String(80), nullable=False),
        sa.Column('entity_type', sa.String(40), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table('room_incidents',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('room_id', sa.Uuid(), sa.ForeignKey('rooms.id'), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('reported_by', sa.Uuid(), sa.ForeignKey('staff_users.id'), nullable=False),
        sa.Column('reported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_by', sa.Uuid(), sa.ForeignKey('staff_users.id'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('restored_by', sa.Uuid(), sa.ForeignKey('staff_users.id'), nullable=True),
        sa.Column('restored_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_room_incidents_room_id', 'room_incidents', ['room_id'])

def downgrade():
    op.drop_index('ix_room_incidents_room_id', table_name='room_incidents')
    op.drop_table('room_incidents')
    op.drop_table('business_audit')
    op.drop_table('staff_users')
