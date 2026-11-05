
"""Almacenamiento auxiliar de CSV ficticios.

No constituye una entidad del dominio del PMS.
"""

from sqlalchemy import CheckConstraint, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.base import Base


class DemoCSVRecordModel(Base):
    __tablename__ = "demo_csv_records"

    source_file: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    source_key: Mapped[str] = mapped_column(
        String(120), primary_key=True
    )
    row_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    payload: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "row_number >= 2",
            name="ck_demo_csv_record_row",
        ),
    )
