
"""Pruebas de la política de cancelación RN-04 / US-05."""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.reservations.policies import (
    individual_cancellation_penalty_nights,
)


HOTEL_TIMEZONE = timezone(timedelta(hours=-6))

ARRIVAL = datetime(
    2026, 12, 10, 15, 0,
    tzinfo=HOTEL_TIMEZONE,
)


def test_cancel_with_more_than_48_hours_is_free():
    assert individual_cancellation_penalty_nights(
        ARRIVAL,
        ARRIVAL - timedelta(hours=72),
    ) == 0


def test_cancel_exactly_48_hours_before_is_free():
    assert individual_cancellation_penalty_nights(
        ARRIVAL,
        ARRIVAL - timedelta(hours=48),
    ) == 0


def test_cancel_less_than_48_hours_has_one_night_penalty():
    assert individual_cancellation_penalty_nights(
        ARRIVAL,
        ARRIVAL - timedelta(hours=47, minutes=59),
    ) == 1


def test_cancel_on_arrival_day_has_one_night_penalty():
    assert individual_cancellation_penalty_nights(
        ARRIVAL,
        ARRIVAL - timedelta(hours=2),
    ) == 1


def test_evaluation_accepts_different_timezones():
    request_in_utc = (
        ARRIVAL - timedelta(hours=48)
    ).astimezone(timezone.utc)

    assert individual_cancellation_penalty_nights(
        ARRIVAL,
        request_in_utc,
    ) == 0


@pytest.mark.parametrize(
    "arrival, request_at",
    [
        (ARRIVAL.replace(tzinfo=None), ARRIVAL),
        (ARRIVAL, ARRIVAL.replace(tzinfo=None)),
    ],
)
def test_reject_naive_datetimes(arrival, request_at):
    with pytest.raises(ValueError, match="zona horaria"):
        individual_cancellation_penalty_nights(
            arrival,
            request_at,
        )
