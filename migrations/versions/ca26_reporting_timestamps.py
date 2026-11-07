"""Tiempos de movimientos nuevos, sin alterar los históricos.

Revision ID: ca26reporting
Revises: ba25exceptions
"""
from alembic import op
import sqlalchemy as sa
revision='ca26reporting'
down_revision='ba25exceptions'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('folio_charges',sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('folio_payments',sa.Column('recorded_at',sa.DateTime(timezone=True),nullable=True))

def downgrade():
    op.drop_column('folio_payments','recorded_at')
    op.drop_column('folio_charges','recorded_at')
