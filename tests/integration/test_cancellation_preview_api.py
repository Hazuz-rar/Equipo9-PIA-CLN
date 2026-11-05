
"""Pruebas HTTP de previsualización de cancelaciones."""

from uuid import uuid4

from tests.integration.test_reservations_api import (
    client,
    valid_reservation,
)


def create_reservation(client):
    response = client.post(
        "/api/v1/reservations",
        json=valid_reservation(),
    )
    assert response.status_code == 201
    return response.json()["id"]


def preview(client, reservation_id, requested_at, arrival_at="2026-12-10T15:00:00-06:00"):
    return client.get(
        f"/api/v1/reservations/{reservation_id}/cancellation-preview",
        params={
            "arrival_at": arrival_at,
            "requested_at": requested_at,
        },
    )


def test_preview_free_cancellation(client):
    reservation_id = create_reservation(client)

    response = preview(
        client,
        reservation_id,
        "2026-12-08T15:00:00-06:00",
    )

    assert response.status_code == 200
    assert response.json()["penalty_nights"] == 0

    found = client.get(
        f"/api/v1/reservations/{reservation_id}"
    )
    assert found.json()["status"] == "SOLICITADA"


def test_preview_penalty_for_confirmed_reservation(client):
    reservation_id = create_reservation(client)

    confirmed = client.patch(
        f"/api/v1/reservations/{reservation_id}/confirm"
    )
    assert confirmed.status_code == 200

    response = preview(
        client,
        reservation_id,
        "2026-12-08T15:01:00-06:00",
    )

    assert response.status_code == 200
    assert response.json()["penalty_nights"] == 1

    found = client.get(
        f"/api/v1/reservations/{reservation_id}"
    )
    assert found.json()["status"] == "CONFIRMADA"


def test_preview_rejects_invalid_arrival_time(client):
    reservation_id = create_reservation(client)

    response = preview(
        client,
        reservation_id,
        "2026-12-08T12:00:00-06:00",
        "2026-12-10T12:00:00-06:00",
    )

    assert response.status_code == 422


def test_preview_rejects_cancelled_reservation(client):
    reservation_id = create_reservation(client)

    cancelled = client.patch(
        f"/api/v1/reservations/{reservation_id}/cancel"
    )
    assert cancelled.status_code == 200

    response = preview(
        client,
        reservation_id,
        "2026-12-08T15:00:00-06:00",
    )

    assert response.status_code == 409


def test_preview_unknown_reservation(client):
    response = preview(
        client,
        uuid4(),
        "2026-12-08T15:00:00-06:00",
    )

    assert response.status_code == 404
