
"""Tabla auxiliar para CSV de prueba.

Revision ID: 4a11csv
Revises: 3a10voucher
"""

from alembic import op
import sqlalchemy as sa

revision = "4a11csv"
down_revision = "3a10voucher"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_csv_records",
        sa.Column(
            "source_file",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "source_key",
            sa.String(120),
            nullable=False,
        ),
        sa.Column(
            "row_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.JSON(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "row_number >= 2",
            name="ck_demo_csv_record_row",
        ),
        sa.PrimaryKeyConstraint(
            "source_file",
            "source_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("demo_csv_records")
