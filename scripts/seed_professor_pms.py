"""Convertir los CSV ya importados en datos operativos FICTICIOS.

Validar (sin cambios): python -m scripts.seed_professor_pms
Importar (requiere aceptación de aforo demostrativo):
  python -m scripts.seed_professor_pms --apply --accept-demo-capacities

NO convierte operaciones sin fechas de estancia en reservas reales.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from src.domain.rooms.entities import RoomStatus
from src.infrastructure.database.models import DemoCSVRecordModel
from src.infrastructure.database.models.demo_operational_model import (
    DemoGuestModel, DemoScenarioModel, DemoScenarioLineModel,
)
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.session import engine
from src.infrastructure.database.demo_seed_ids import stable_id

# APROXIMACIONES EXCLUSIVAMENTE PARA PRUEBAS. No son política del hotel ni
# equivalen a la columna capacidad_o_stock de los CSV del docente.
DEMO_GUEST_CAPACITY = {"Estándar": 2, "Doble": 2, "Suite": 4, "Familiar": 4}
COUNTS = {
    "actores.csv": 40,
    "catalogo.csv": 20,
    "operaciones.csv": 60,
    "detalle_operaciones.csv": 117,
    "casos_prueba.csv": 120,
    "transiciones_prueba.csv": 20,
}


def load_staged(session: Session):
    rows = session.scalars(
        select(DemoCSVRecordModel).order_by(
            DemoCSVRecordModel.source_file, DemoCSVRecordModel.row_number
        )
    ).all()
    files = defaultdict(list)
    for row in rows:
        files[row.source_file].append(row.payload)
    counts = {name: len(files[name]) for name in COUNTS}
    if counts != COUNTS:
        raise ValueError(
            f"Se requieren los 377 registros completos en demo_csv_records. "
            f"Encontrados: {counts}. Ejecuta primero scripts.import_demo_csv."
        )
    return files


def as_flag(value, label):
    if str(value) not in ("0", "1"):
        raise ValueError(f"{label} debe ser 0 o 1, recibido {value!r}")
    return str(value) == "1"


def prepare(files):
    guests, rooms, scenarios, lines = [], [], [], []
    actors = {}
    resources = {}
    for actor in files["actores.csv"]:
        aid = actor["actor_id"]
        if aid in actors:
            raise ValueError(f"Actor duplicado: {aid}")
        actors[aid] = actor
        guests.append(DemoGuestModel(
            id=stable_id("guest", aid), source_actor_id=aid,
            display_name=actor["nombre"], city=actor["ciudad"],
            is_preferred=as_flag(actor["es_preferente"], "es_preferente"),
            is_active=as_flag(actor["activo"], "activo"),
        ))
    for resource in files["catalogo.csv"]:
        source_id = resource["recurso_id"]
        if source_id in resources:
            raise ValueError(f"Recurso duplicado: {source_id}")
        resources[source_id] = resource
        number_part = source_id.rsplit("P", 1)[-1]
        room_type = resource["descripcion"].rsplit(" ", 1)[0]
        if room_type not in DEMO_GUEST_CAPACITY:
            raise ValueError(f"Tipo no reconocido para {source_id}: {room_type}")
        try:
            rate = Decimal(resource["precio_mxn"])
            stock = int(resource["capacidad_o_stock"])
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Tarifa o stock inválido: {source_id}") from exc
        if not rate.is_finite() or rate < 0 or stock < 0:
            raise ValueError(f"Tarifa/stock fuera de rango: {source_id}")
        enabled = as_flag(resource["habilitado"], "habilitado")
        rooms.append(RoomModel(
            id=stable_id("room", source_id),
            number=f"P-{number_part}",
            room_type=room_type,
            capacity=DEMO_GUEST_CAPACITY[room_type],
            base_rate=rate,
            status=RoomStatus.AVAILABLE if enabled else RoomStatus.OUT_OF_ORDER,
        ))
    by_operation = defaultdict(list)
    seen_lines = set()
    for detail in files["detalle_operaciones.csv"]:
        oid, source_id = detail["operacion_id"], detail["recurso_id"]
        if source_id not in resources:
            raise ValueError(f"Recurso no encontrado: {source_id}")
        key = (oid, source_id)
        if key in seen_lines:
            raise ValueError(f"Línea duplicada: {key}")
        seen_lines.add(key)
        quantity = int(detail["cantidad"])
        if quantity <= 0:
            raise ValueError(f"Cantidad inválida en {key}")
        line = DemoScenarioLineModel(
            operation_id=oid, source_resource_id=source_id,
            room_id=stable_id("room", source_id), quantity=quantity,
            unit_price_mxn=Decimal(resources[source_id]["precio_mxn"]),
        )
        by_operation[oid].append(line)
        lines.append(line)
    seen_ops = set()
    for operation in files["operaciones.csv"]:
        oid, aid = operation["operacion_id"], operation["actor_id"]
        if oid in seen_ops or aid not in actors:
            raise ValueError(f"Operación duplicada o actor no encontrado: {oid}")
        seen_ops.add(oid)
        rows = by_operation[oid]
        total = sum((r.unit_price_mxn * r.quantity for r in rows), Decimal("0.00"))
        scenarios.append(DemoScenarioModel(
            operation_id=oid, guest_id=stable_id("guest", aid),
            requested_at=date.fromisoformat(operation["fecha_solicitud"]),
            initial_state=operation["estado_inicial"],
            reference=operation["referencia"],
            authorized=as_flag(operation["autorizado"], "autorizado"),
            promotion_active=as_flag(operation["promocion_activa"], "promocion_activa"),
            line_count=len(rows), example_total_mxn=total,
        ))
    if any(line.operation_id not in seen_ops for line in lines):
        raise ValueError("Hay detalles que no pertenecen a una operación")
    return guests, rooms, scenarios, lines


def seed(session: Session, *, apply: bool = False, confirmed: bool = False):
    files = load_staged(session)
    guests, rooms, scenarios, lines = prepare(files)
    outcome = {
        "huespedes_ficticios": len(guests), "habitaciones_ficticias": len(rooms),
        "escenarios": len(scenarios), "lineas": len(lines),
        "casos_de_prueba_en_stage": len(files["casos_prueba.csv"]),
        "transiciones_en_stage": len(files["transiciones_prueba.csv"]),
        "operaciones_sin_detalle": [s.operation_id for s in scenarios if s.line_count == 0],
    }
    if not apply:
        return outcome
    if not confirmed:
        raise ValueError(
            "Para importar habitaciones, usa --accept-demo-capacities: "
            "2 Estándar, 2 Doble, 4 Suite, 4 Familiar son aforos supuestos de prueba."
        )
    existing_room_by_id = {r.id: r for r in session.scalars(select(RoomModel))}
    existing_room_by_number = {r.number: r for r in existing_room_by_id.values()}
    existing_guests_by_id = {g.id: g for g in session.scalars(select(DemoGuestModel))}
    existing_guests_by_source = {g.source_actor_id: g for g in existing_guests_by_id.values()}
    existing_scenarios = set(session.scalars(select(DemoScenarioModel.operation_id)))
    existing_lines = set(session.execute(select(DemoScenarioLineModel.operation_id, DemoScenarioLineModel.source_resource_id)))
    added = Counter()
    for guest in guests:
        existing = existing_guests_by_source.get(guest.source_actor_id)
        if existing is not None and existing.id != guest.id:
            raise ValueError(f"Colisión de actor del profesor: {guest.source_actor_id}")
        if guest.id not in existing_guests_by_id:
            session.add(guest); added["guests"] += 1
    session.flush()
    for room in rooms:
        existing = existing_room_by_number.get(room.number)
        if existing is not None and existing.id != room.id:
            raise ValueError(f"Ya existe una habitación ajena con número {room.number}. No se modificó.")
        if room.id not in existing_room_by_id:
            session.add(room); added["rooms"] += 1
    session.flush()
    for scenario in scenarios:
        if scenario.operation_id not in existing_scenarios:
            session.add(scenario); added["scenarios"] += 1
    session.flush()
    for line in lines:
        if (line.operation_id, line.source_resource_id) not in existing_lines:
            session.add(line); added["lines"] += 1
    session.flush()
    outcome["nuevos"] = dict(added)
    return outcome


def main():
    parser = argparse.ArgumentParser(description="CSV del profesor -> datos del PMS, SIN reservas automáticas")
    parser.add_argument("--apply", action="store_true", help="Guardar cambios de modo transaccional")
    parser.add_argument("--accept-demo-capacities", action="store_true",
                        help="Acepto aforos demostrativos; no son políticas oficiales")
    args = parser.parse_args()
    required = {"demo_csv_records", "rooms", "demo_guests", "demo_scenarios", "demo_scenario_lines"}
    missing = required - set(inspect(engine).get_table_names())
    if missing:
        parser.error(f"Faltan tablas {sorted(missing)}. Ejecuta primero alembic upgrade head.")
    with Session(engine) as session:
        with session.begin():
            result = seed(session, apply=args.apply, confirmed=args.accept_demo_capacities)
        for k, v in result.items():
            print(f"{k}: {v}")
        print("IMPORTACIÓN APLICADA" if args.apply else "VISTA PREVIA; SIN CAMBIOS")


if __name__ == "__main__":
    main()
