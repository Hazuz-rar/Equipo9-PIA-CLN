"""Lectura autenticada de datos ficticios del profesor; nunca ejecuta operaciones de negocio."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.core.security import require_roles
from src.infrastructure.database.models.demo_csv_model import DemoCSVRecordModel
from src.infrastructure.database.demo_seed_ids import stable_id
from src.infrastructure.database.models.demo_operational_model import (
    DemoGuestModel, DemoScenarioLineModel, DemoScenarioModel,
)
from src.infrastructure.database.models.room_model import RoomModel

router = APIRouter(dependencies=[Depends(require_roles(
    "RECEPTION", "RESERVATIONS", "FINANCE", "MANAGER_RECEPTION", "MANAGER_OPERATIONS",
))])


@router.get("/guests")
def guests(
    active_only: bool = False,
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_db),
):
    query = select(DemoGuestModel).order_by(DemoGuestModel.source_actor_id).limit(limit)
    if active_only:
        query = query.where(DemoGuestModel.is_active.is_(True))
    return [{
        "id": str(g.id), "source_actor_id": g.source_actor_id,
        "name": g.display_name, "city": g.city,
        "is_preferred": g.is_preferred, "is_active": g.is_active,
    } for g in session.scalars(query)]


@router.get("/rooms")
def demo_rooms(session: Session = Depends(get_db)):
    # Catálogo originado en el CSV y ya guardado en la tabla operativa rooms.
    staged = session.scalars(select(DemoCSVRecordModel).where(
        DemoCSVRecordModel.source_file == "catalogo.csv"
    ).order_by(DemoCSVRecordModel.row_number))
    result = []
    for row in staged:
        room = session.get(RoomModel, stable_id("room", row.source_key))
        if room is not None:
            result.append({
                "id": str(room.id), "source_resource_id": row.source_key,
                "number": room.number, "room_type": room.room_type,
                "capacity": room.capacity, "base_rate": str(room.base_rate),
                "status": room.status.value,
                "source_capacity_or_stock": row.payload["capacidad_o_stock"],
            })
    return result


@router.get("/scenarios")
def scenarios(
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_db),
):
    rows = session.execute(
        select(DemoScenarioModel, DemoGuestModel)
        .join(DemoGuestModel, DemoScenarioModel.guest_id == DemoGuestModel.id)
        .order_by(DemoScenarioModel.operation_id).limit(limit)
    )
    return [{
        "operation_id": s.operation_id, "guest_id": str(s.guest_id),
        "guest_name": g.display_name, "guest_active": g.is_active,
        "authorized": s.authorized, "promotion_active": s.promotion_active,
        "initial_state": s.initial_state, "requested_at": s.requested_at.isoformat(),
        "reference": s.reference, "line_count": s.line_count,
        "example_total_mxn": str(s.example_total_mxn),
        "processability_example": bool(g.is_active and s.line_count and s.authorized),
    } for s, g in rows]


@router.get("/scenarios/{operation_id}")
def scenario_detail(operation_id: str, session: Session = Depends(get_db)):
    record = session.get(DemoScenarioModel, operation_id)
    if record is None:
        raise HTTPException(404, "Escenario de prueba no encontrado")
    lines = session.execute(
        select(DemoScenarioLineModel, RoomModel)
        .join(RoomModel, RoomModel.id == DemoScenarioLineModel.room_id)
        .where(DemoScenarioLineModel.operation_id == operation_id)
        .order_by(DemoScenarioLineModel.source_resource_id)
    )
    return {
        "operation_id": record.operation_id,
        "guest_id": str(record.guest_id),
        "date_note": "No incluye fechas de entrada y salida: NO es una reserva creada.",
        "example_total_mxn": str(record.example_total_mxn),
        "lines": [{
            "source_resource_id": line.source_resource_id,
            "room_id": str(room.id), "room_number": room.number,
            "quantity": line.quantity, "unit_price_mxn": str(line.unit_price_mxn),
            "line_total_mxn": str(line.quantity * line.unit_price_mxn),
        } for line, room in lines],
    }


@router.get("/test-cases")
def test_cases(
    limit: int = Query(200, ge=1, le=200),
    session: Session = Depends(get_db),
):
    rows = session.scalars(select(DemoCSVRecordModel).where(
        DemoCSVRecordModel.source_file == "casos_prueba.csv"
    ).order_by(DemoCSVRecordModel.row_number).limit(limit))
    return [r.payload for r in rows]


@router.get("/transitions")
def transitions(
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_db),
):
    rows = session.scalars(select(DemoCSVRecordModel).where(
        DemoCSVRecordModel.source_file == "transiciones_prueba.csv"
    ).order_by(DemoCSVRecordModel.row_number).limit(limit))
    return [r.payload for r in rows]
