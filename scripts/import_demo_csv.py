
"""Importación de los CSV ficticios del Hotel Costa Azul.

Validar:
python -m scripts.import_demo_csv --zip "09_Hotel_Costa_Azul(1).zip"

Importar:
python -m scripts.import_demo_csv --zip "09_Hotel_Costa_Azul(1).zip" --apply
"""

import argparse
import csv
import io

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.infrastructure.database.models.demo_csv_model import (
    DemoCSVRecordModel,
)


CSV_SPECS = {
    "actores.csv": (
        ("actor_id", "nombre", "es_preferente", "activo", "ciudad"),
        ("actor_id",),
    ),
    "catalogo.csv": (
        (
            "recurso_id",
            "descripcion",
            "precio_mxn",
            "capacidad_o_stock",
            "habilitado",
        ),
        ("recurso_id",),
    ),
    "operaciones.csv": (
        (
            "operacion_id",
            "actor_id",
            "estado_inicial",
            "fecha_solicitud",
            "promocion_activa",
            "autorizado",
            "referencia",
        ),
        ("operacion_id",),
    ),
    "detalle_operaciones.csv": (
        ("operacion_id", "recurso_id", "cantidad"),
        ("operacion_id", "recurso_id"),
    ),
    "casos_prueba.csv": (
        (
            "caso_id",
            "operacion_id",
            "tipo_prueba",
            "regla_a_verificar",
            "resultado_alumno",
            "instrucciones",
        ),
        ("caso_id",),
    ),
    "transiciones_prueba.csv": (
        (
            "caso_id",
            "operacion_id",
            "accion_sugerida",
            "estado_inicial",
            "resultado_alumno",
            "instrucciones",
        ),
        ("caso_id",),
    ),
}


def load_csv_bundle(zip_path: Path) -> dict[str, list[dict]]:
    records = {}

    with ZipFile(zip_path) as archive:
        for filename, (columns, key_columns) in CSV_SPECS.items():

            suffix = "/01_Alumno/datos/" + filename

            matches = [
                name
                for name in archive.namelist()
                if name.endswith(suffix)
            ]

            if len(matches) != 1:
                raise ValueError(
                    f"Falta o está duplicado el archivo: {filename}"
                )

            with archive.open(matches[0]) as binary:
                reader = csv.DictReader(
                    io.TextIOWrapper(
                        binary,
                        encoding="utf-8-sig",
                        newline="",
                    )
                )

                if tuple(reader.fieldnames or ()) != columns:
                    raise ValueError(
                        f"Columnas inesperadas en {filename}: "
                        f"{reader.fieldnames}"
                    )

                file_records = []
                seen = set()

                for row_number, row in enumerate(reader, start=2):

                    if None in row or any(
                        value is None for value in row.values()
                    ):
                        raise ValueError(
                            f"CSV mal formado: {filename}, "
                            f"línea {row_number}"
                        )

                    key_parts = [
                        row[field].strip()
                        for field in key_columns
                    ]

                    if not all(key_parts):
                        raise ValueError(
                            f"Clave vacía en {filename}, "
                            f"línea {row_number}"
                        )

                    key = "|".join(key_parts)

                    if key in seen:
                        raise ValueError(
                            f"Clave duplicada en {filename}: {key}"
                        )

                    seen.add(key)

                    file_records.append({
                        "source_file": filename,
                        "source_key": key,
                        "row_number": row_number,
                        "payload": row,
                    })

                records[filename] = file_records

    def ids(filename, column):
        return {
            item["payload"][column]
            for item in records[filename]
        }

    actor_ids = ids("actores.csv", "actor_id")
    resource_ids = ids("catalogo.csv", "recurso_id")
    operation_ids = ids("operaciones.csv", "operacion_id")

    relationships = (
        ("operaciones.csv", "actor_id", actor_ids),
        ("detalle_operaciones.csv", "operacion_id", operation_ids),
        ("detalle_operaciones.csv", "recurso_id", resource_ids),
        ("casos_prueba.csv", "operacion_id", operation_ids),
        ("transiciones_prueba.csv", "operacion_id", operation_ids),
    )

    for filename, field, allowed in relationships:
        for item in records[filename]:
            if item["payload"][field] not in allowed:
                raise ValueError(
                    f"Referencia inexistente: {filename}, "
                    f"línea {item['row_number']}, {field}"
                )

    for item in records["catalogo.csv"]:
        try:
            amount = Decimal(item["payload"]["precio_mxn"])
            stock = int(item["payload"]["capacidad_o_stock"])

            if (
                not amount.is_finite()
                or amount < 0
                or stock < 0
            ):
                raise ValueError()

        except (ValueError, InvalidOperation) as error:
            raise ValueError(
                f"Catálogo numérico inválido en "
                f"línea {item['row_number']}"
            ) from error

    for item in records["detalle_operaciones.csv"]:
        try:
            if int(item["payload"]["cantidad"]) <= 0:
                raise ValueError()
        except ValueError as error:
            raise ValueError(
                f"Cantidad inválida en línea {item['row_number']}"
            ) from error

    for item in records["operaciones.csv"]:
        try:
            date.fromisoformat(
                item["payload"]["fecha_solicitud"]
            )
        except ValueError as error:
            raise ValueError(
                f"Fecha inválida en línea {item['row_number']}"
            ) from error

    return records


def import_records(engine, data):
    table = DemoCSVRecordModel.__table__

    with engine.begin() as connection:

        if not inspect(connection).has_table(table.name):
            raise RuntimeError(
                "Falta demo_csv_records. "
                "Ejecuta Alembic upgrade head."
            )

        dialect = connection.dialect.name

        if dialect not in ("postgresql", "sqlite"):
            raise RuntimeError(
                f"Motor no compatible: {dialect}"
            )

        for filename, items in data.items():

            for start in range(0, len(items), 100):
                batch = items[start:start + 100]

                if not batch:
                    continue

                if dialect == "postgresql":
                    statement = pg_insert(table).values(batch)
                else:
                    statement = sqlite_insert(table).values(batch)

                statement = statement.on_conflict_do_update(
                    index_elements=[
                        table.c.source_file,
                        table.c.source_key,
                    ],
                    set_={
                        "row_number": statement.excluded.row_number,
                        "payload": statement.excluded.payload,
                    },
                )

                connection.execute(statement)


def main():
    parser = argparse.ArgumentParser(
        description="Importar CSV de demostración del hotel"
    )

    parser.add_argument(
        "--zip",
        required=True,
        type=Path,
        help="Ruta del ZIP de datos",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Guardar los registros en PostgreSQL",
    )

    args = parser.parse_args()

    data = load_csv_bundle(args.zip)

    for filename, items in data.items():
        print(f"{filename}: {len(items)} registros")

    total = sum(len(items) for items in data.values())
    print(f"TOTAL: {total} registros")

    operation_ids = {
        item["source_key"]
        for item in data["operaciones.csv"]
    }

    operations_with_detail = {
        item["payload"]["operacion_id"]
        for item in data["detalle_operaciones.csv"]
    }

    missing = sorted(
        operation_ids - operations_with_detail
    )

    print(
        "Operaciones sin detalle:",
        ", ".join(missing) if missing else "ninguna",
    )

    if not args.apply:
        print(
            "VALIDACIÓN COMPLETA. "
            "No se modificó la base de datos."
        )
        return

    from src.core.config import settings

    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    try:
        if engine.dialect.name != "postgresql":
            raise RuntimeError(
                "La importación real requiere PostgreSQL."
            )

        import_records(engine, data)

        table = DemoCSVRecordModel.__table__

        with engine.connect() as connection:
            count = connection.scalar(
                select(func.count()).select_from(table)
            )

        print(
            f"IMPORTACIÓN COMPLETA. "
            f"Filas en tabla auxiliar: {count}"
        )

        print(
            "No se modificaron las tablas "
            "reservations ni folios."
        )

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
