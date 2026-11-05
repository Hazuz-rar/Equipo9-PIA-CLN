
"""Pruebas HTTP de consulta de folios."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.core.config import settings
from src.domain.folios.entities import Folio
from src.domain.folios.value_objects import (
    ChargeAmount,
    FolioId,
    PaymentAmount,
    ReservationReference,
)
from src.infrastructure.database.base import Base
from src.infrastructure.database import models  # noqa: F401
from src.infrastructure.repositories.sqlalchemy_folio_repository import (
    SQLAlchemyFolioRepository,
)
from src.main import app


@pytest.fixture
def api_context():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

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


def create_folio(client, engine, closed=False):
    response = client.post(
        "/api/v1/reservations",
        json={
            "guest_id": str(uuid4()),
            "room_id": str(uuid4()),
            "check_in": "2026-12-10",
            "check_out": "2026-12-13",
        },
    )

    assert response.status_code == 201, response.text

    reservation_id = response.json()["id"]

    with Session(engine) as session:
        folio = Folio(
            id=FolioId(uuid4()),
            reservation_id=ReservationReference(
                UUID(reservation_id)
            ),
        )

        folio.add_charge(
            "Hospedaje",
            ChargeAmount(Decimal("300.00")),
        )

        folio.add_payment(
            "Abono",
            PaymentAmount(Decimal("120.00")),
        )

        if closed:
            folio.add_payment(
                "Liquidación",
                PaymentAmount(Decimal("180.00")),
            )
            folio.close()

        repository = SQLAlchemyFolioRepository(session)
        repository.add(folio)
        session.commit()

        return folio.id.value


def test_get_folio_shows_charges_payments_and_balance(
    api_context,
):
    client, engine = api_context
    folio_id = create_folio(client, engine)

    response = client.get(
        f"/api/v1/folios/{folio_id}"
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == str(folio_id)
    assert data["status"] == "ABIERTO"
    assert len(data["charges"]) == 1
    assert data["charges"][0]["description"] == "Hospedaje"
    assert Decimal(data["total_charges"]) == Decimal("300")
    assert Decimal(data["total_payments"]) == Decimal("120")
    assert Decimal(data["balance"]) == Decimal("180")


def test_get_closed_folio(api_context):
    client, engine = api_context
    folio_id = create_folio(client, engine, closed=True)

    response = client.get(
        f"/api/v1/folios/{folio_id}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CERRADO"
    assert Decimal(response.json()["balance"]) == Decimal("0")


def test_get_folio_not_found(api_context):
    client, _ = api_context

    response = client.get(
        f"/api/v1/folios/{uuid4()}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "El folio no existe."


def test_get_folio_invalid_uuid(api_context):
    client, _ = api_context

    response = client.get(
        "/api/v1/folios/no-es-un-uuid"
    )

    assert response.status_code == 422


def test_folio_read_is_disabled_in_production(
    api_context,
    monkeypatch,
):
    client, engine = api_context
    folio_id = create_folio(client, engine)

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        f"/api/v1/folios/{folio_id}"
    )

    assert response.status_code == 403
