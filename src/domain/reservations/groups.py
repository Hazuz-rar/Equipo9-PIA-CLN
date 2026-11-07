"""Política RN-07/US-22. Los días se miden en fechas civiles locales del hotel."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def required_group_deposit(room_count: int, total: Decimal) -> Decimal:
    if room_count < 10:
        raise ValueError('Una reserva grupal requiere al menos 10 habitaciones.')
    if not isinstance(total, Decimal) or not total.is_finite() or total <= 0:
        raise ValueError('El importe de la reserva grupal debe ser positivo.')
    return (total * Decimal('0.30')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def group_deposit_refundable(check_in: date, cancellation_date: date) -> bool:
    return (check_in - cancellation_date) >= timedelta(days=7)
