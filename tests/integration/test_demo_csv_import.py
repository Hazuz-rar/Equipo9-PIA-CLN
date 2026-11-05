
"""Pruebas del importador sin usar PostgreSQL real."""

import csv
import io

from zipfile import ZipFile

import pytest

from sqlalchemy import create_engine, func, select

from scripts.import_demo_csv import (
    CSV_SPECS,
    import_records,
    load_csv_bundle,
)

from src.infrastructure.database.models.demo_csv_model import (
    DemoCSVRecordModel,
)


ROWS = {
    "actores.csv": [
        "HOT-C001", "Huésped ficticio",
        "0", "1", "Monterrey",
    ],
    "catalogo.csv": [
        "HOT-P001", "Habitación demostración",
        "900.00", "2", "1",
    ],
    "operaciones.csv": [
        "HOT-O001", "HOT-C001", "SOLICITADA",
        "2026-10-02", "0", "1", "DEMO-01",
    ],
    "detalle_operaciones.csv": [
        "HOT-O001", "HOT-P001", "2",
    ],
    "casos_prueba.csv": [
        "HOT-T001", "HOT-O001", "validar",
        "regla ilustrativa", "PENDIENTE", "Probar",
    ],
    "transiciones_prueba.csv": [
        "HOT-S001", "HOT-O001", "confirmar",
        "SOLICITADA", "PENDIENTE", "Probar",
    ],
}


def make_zip(tmp_path, overrides=None):
    path = tmp_path / "demo.zip"
    overrides = overrides or {}

    with ZipFile(path, "w") as archive:
        for filename, (columns, _) in CSV_SPECS.items():
            data = io.StringIO(newline="")
            writer = csv.writer(data)

            writer.writerow(columns)
            writer.writerow(
                overrides.get(filename, ROWS[filename])
            )

            archive.writestr(
                "09_Hotel_Costa_Azul/01_Alumno/datos/"
                + filename,
                data.getvalue().encode("utf-8-sig"),
            )

    return path


def test_loads_all_six_csv_files(tmp_path):
    data = load_csv_bundle(make_zip(tmp_path))

    assert len(data) == 6
    assert sum(map(len, data.values())) == 6

    assert (
        data["detalle_operaciones.csv"][0]["source_key"]
        == "HOT-O001|HOT-P001"
    )


def test_upsert_reimport_does_not_duplicate(tmp_path):
    data = load_csv_bundle(make_zip(tmp_path))

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    DemoCSVRecordModel.__table__.create(engine)

    import_records(engine, data)
    import_records(engine, data)

    with engine.connect() as connection:
        count = connection.scalar(
            select(func.count()).select_from(
                DemoCSVRecordModel.__table__
            )
        )

        assert count == 6

    engine.dispose()


def test_rejects_missing_actor_reference(tmp_path):
    row = ROWS["operaciones.csv"].copy()
    row[1] = "NO-EXISTE"

    with pytest.raises(
        ValueError,
        match="Referencia inexistente",
    ):
        load_csv_bundle(
            make_zip(
                tmp_path,
                {"operaciones.csv": row},
            )
        )


def test_rejects_negative_quantity(tmp_path):
    with pytest.raises(
        ValueError,
        match="Cantidad inválida",
    ):
        load_csv_bundle(
            make_zip(
                tmp_path,
                {
                    "detalle_operaciones.csv": [
                        "HOT-O001", "HOT-P001", "-2"
                    ],
                },
            )
        )


def test_import_fails_before_creating_unversioned_table(
    tmp_path,
):
    data = load_csv_bundle(make_zip(tmp_path))

    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    with pytest.raises(
        RuntimeError,
        match="Alembic",
    ):
        import_records(engine, data)

    engine.dispose()
