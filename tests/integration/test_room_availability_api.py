
"""Pruebas de disponibilidad de habitaciones: US-02."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.domain.reservations.entities import ReservationStatus
from src.domain.reservations.value_objects import RoomId
from src.domain.rooms.entities import Room, RoomStatus
from src.domain.rooms.value_objects import (
    RoomNumber,
    Capacity,
    Money,
)
from src.infrastructure.database.base import Base
from src.infrastructure.database import models
from src.infrastructure.database.models.reservation_model import (
    ReservationModel,
)
from src.infrastructure.repositories.sqlalchemy_room_repository import (
    SQLAlchemyRoomRepository,
)
from src.main import app


@pytest.fixture
def context():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def seed_room(
    engine,
    number="101",
    room_type="Estándar",
    capacity=2,
    status=RoomStatus.AVAILABLE,
):
    room_id = uuid4()

    with Session(engine) as session:
        repository = SQLAlchemyRoomRepository(session)

        repository.add(
            room_id,
            Room(
                number=RoomNumber(number),
                room_type=room_type,
                capacity=Capacity(capacity),
                base_rate=Money(Decimal("1250.00")),
                status=status,
            ),
        )

        session.commit()

    return room_id


def query(
    client,
    start="2026-12-10",
    end="2026-12-13",
    **filters,
):
    return client.get(
        "/api/v1/rooms/available",
        params={
            "check_in": start,
            "check_out": end,
            **filters,
        },
    )


def seed_reservation(
    engine,
    room_id,
    status,
    start="2026-12-11",
    end="2026-12-14",
):
    with Session(engine) as session:
        session.add(
            ReservationModel(
                id=uuid4(),
                guest_id=uuid4(),
                room_id=room_id,
                check_in=date.fromisoformat(start),
                check_out=date.fromisoformat(end),
                status=status,
            )
        )
        session.commit()


def test_empty_catalog_returns_empty_list(context):
    client, _ = context

    response = query(client)

    assert response.status_code == 200
    assert response.json() == []


def test_room_can_be_persisted_and_queried(context):
    client, engine = context

    room_id = seed_room(engine)
    response = query(client)

    assert response.status_code == 200, response.text

    assert response.json() == [
        {
            "id": str(room_id),
            "number": "101",
            "room_type": "Estándar",
            "capacity": 2,
            "base_rate": "1250.00",
            "currency": "MXN",
        }
    ]

    with Session(engine) as session:
        room = SQLAlchemyRoomRepository(
            session
        ).get_by_id(RoomId(room_id))

        assert room.number.value == "101"
        assert room.status == RoomStatus.AVAILABLE


def test_filters_by_room_type_and_capacity(context):
    client, engine = context

    seed_room(engine, "101", "Estándar", 2)
    suite = seed_room(engine, "201", "Suite", 4)

    response = query(
        client,
        room_type="suite",
        guests=3,
    )

    assert response.status_code == 200
    assert [x["id"] for x in response.json()] == [
        str(suite)
    ]


def test_out_of_order_and_occupied_are_not_offered(
    context,
):
    client, engine = context

    seed_room(
        engine,
        "101",
        status=RoomStatus.OUT_OF_ORDER,
    )

    seed_room(
        engine,
        "102",
        status=RoomStatus.OCCUPIED,
    )

    assert query(client).json() == []


def test_confirmed_overlapping_reservation_blocks_room(
    context,
):
    client, engine = context

    room_id = seed_room(engine)

    seed_reservation(
        engine,
        room_id,
        ReservationStatus.CONFIRMED,
    )

    assert query(client).json() == []


def test_checked_in_overlapping_reservation_blocks_room(
    context,
):
    client, engine = context

    room_id = seed_room(engine)

    seed_reservation(
        engine,
        room_id,
        ReservationStatus.CHECK_IN,
    )

    assert query(client).json() == []


def test_requested_and_cancelled_dont_block_room(
    context,
):
    client, engine = context

    room_id = seed_room(engine)

    seed_reservation(
        engine,
        room_id,
        ReservationStatus.REQUESTED,
    )

    seed_reservation(
        engine,
        room_id,
        ReservationStatus.CANCELLED,
    )

    assert [
        x["id"] for x in query(client).json()
    ] == [str(room_id)]


def test_adjacent_dates_are_available(context):
    client, engine = context

    room_id = seed_room(engine)

    seed_reservation(
        engine,
        room_id,
        ReservationStatus.CONFIRMED,
    )

    response = query(
        client,
        "2026-12-14",
        "2026-12-15",
    )

    assert [
        x["id"] for x in response.json()
    ] == [str(room_id)]


def test_invalid_stay_dates_rejected(context):
    client, _ = context

    response = query(
        client,
        start="2026-12-14",
        end="2026-12-10",
    )

    assert response.status_code == 422


def test_invalid_guest_count_rejected(context):
    client, _ = context

    response = query(
        client,
        guests=0,
    )

    assert response.status_code == 422
