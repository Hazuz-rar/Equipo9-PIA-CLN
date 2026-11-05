
"""Crear tablas de folios, cargos y pagos."""

from alembic import op
import sqlalchemy as sa

revision = "2a7folios"
down_revision = "df2b9f82a651"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "folios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "reservation_id", sa.Uuid(), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN",
                "CLOSED",
                name="folio_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id"], ["reservations.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_folios_reservation_id",
        "folios",
        ["reservation_id"],
    )

    op.create_table(
        "folio_charges",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("folio_id", sa.Uuid(), nullable=False),
        sa.Column(
            "description", sa.String(500), nullable=False
        ),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ["folio_id"], ["folios.id"]
        ),
    )

    op.create_index(
        "ix_folio_charges_folio_id",
        "folio_charges",
        ["folio_id"],
    )

    op.create_table(
        "folio_payments",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("folio_id", sa.Uuid(), nullable=False),
        sa.Column(
            "description", sa.String(500), nullable=False
        ),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(
            ["folio_id"], ["folios.id"]
        ),
    )

    op.create_index(
        "ix_folio_payments_folio_id",
        "folio_payments",
        ["folio_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_folio_payments_folio_id",
        table_name="folio_payments",
    )
    op.drop_table("folio_payments")

    op.drop_index(
        "ix_folio_charges_folio_id",
        table_name="folio_charges",
    )
    op.drop_table("folio_charges")

    op.drop_index(
        "ix_folios_reservation_id",
        table_name="folios",
    )
    op.drop_table("folios")
