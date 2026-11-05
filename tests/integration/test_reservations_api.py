"""Pruebas HTTP de reservaciones con base de datos efímera.

Trazabilidad básica: US-04 (crear/confirmar) y consulta individual de reservas.
No sustituyen la prueba de concurrencia y disponibilidad de US-25.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.infrastructure.database.base import Base
from src.infrastructure.database.models.reservation_model import ReservationModel  # noqa: F401
from src.main import app


@pytest.fixture
def client():
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
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def valid_reservation():
    return {
        "guest_id": str(uuid4()),
        "room_id": str(uuid4()),
        "check_in": "2026-12-10",
        "check_out": "2026-12-13",
    }


def test_create_get_and_confirm_reservation(client):
    payload = valid_reservation()
    created = client.post("/api/v1/reservations", json=payload)
    assert created.status_code == 201, created.text
    reservation = created.json()
    assert reservation["status"] == "SOLICITADA"
    assert reservation["guest_id"] == payload["guest_id"]

    found = client.get(f"/api/v1/reservations/{reservation['id']}")
    assert found.status_code == 200
    assert found.json() == reservation

    confirmed = client.patch(f"/api/v1/reservations/{reservation['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMADA"


def test_cancel_requested_reservation(client):
    created = client.post("/api/v1/reservations", json=valid_reservation())
    assert created.status_code == 201
    reservation_id = created.json()["id"]

    cancelled = client.patch(f"/api/v1/reservations/{reservation_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELADA"


def test_nonexistent_reservation_returns_404(client):
    reservation_id = uuid4()
    response = client.get(f"/api/v1/reservations/{reservation_id}")
    assert response.status_code == 404

    confirm = client.patch(f"/api/v1/reservations/{reservation_id}/confirm")
    assert confirm.status_code == 404

    cancel = client.patch(f"/api/v1/reservations/{reservation_id}/cancel")
    assert cancel.status_code == 404


def test_reject_invalid_stay_dates(client):
    payload = valid_reservation()
    payload["check_out"] = payload["check_in"]
    response = client.post("/api/v1/reservations", json=payload)
    assert response.status_code == 422


def test_reject_second_confirmation_for_overlapping_stay(client):
    first_payload = valid_reservation()

    second_payload = dict(first_payload)
    second_payload["guest_id"] = str(uuid4())
    second_payload["check_in"] = "2026-12-11"
    second_payload["check_out"] = "2026-12-14"

    first = client.post(
        "/api/v1/reservations",
        json=first_payload,
    )
    second = client.post(
        "/api/v1/reservations",
        json=second_payload,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    first_id = first.json()["id"]
    second_id = second.json()["id"]

    confirmed = client.patch(
        f"/api/v1/reservations/{first_id}/confirm"
    )
    assert confirmed.status_code == 200

    rejected = client.patch(
        f"/api/v1/reservations/{second_id}/confirm"
    )
    assert rejected.status_code == 409
    assert "reserva activa" in rejected.json()["detail"]

    found = client.get(
        f"/api/v1/reservations/{second_id}"
    )
    assert found.status_code == 200
    assert found.json()["status"] == "SOLICITADA"


def test_allow_adjacent_stays_for_same_room(client):
    first_payload = valid_reservation()

    second_payload = dict(first_payload)
    second_payload["guest_id"] = str(uuid4())
    second_payload["check_in"] = "2026-12-13"
    second_payload["check_out"] = "2026-12-15"

    ids = []

    for payload in (first_payload, second_payload):
        response = client.post(
            "/api/v1/reservations",
            json=payload,
        )
        assert response.status_code == 201
        ids.append(response.json()["id"])

    for reservation_id in ids:
        response = client.patch(
            f"/api/v1/reservations/{reservation_id}/confirm"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CONFIRMADA"
