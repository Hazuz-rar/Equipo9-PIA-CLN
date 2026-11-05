
"""Política de cancelación individual: RN-01, RN-04 y US-05.

Este módulo determina si corresponde penalización.
No realiza cargos, reembolsos ni cambios de estado.
Las reservas grupales utilizan otra política (RN-07).
"""

from datetime import datetime, timedelta


FREE_CANCELLATION_WINDOW = timedelta(hours=48)


def individual_cancellation_penalty_nights(
    arrival_at: datetime,
    requested_at: datetime,
) -> int:
    """Devuelve 0 si es gratuita o 1 si se penaliza una noche.

    Las fechas deben incluir zona horaria.
    arrival_at representa la llegada a las 15:00, hora local.
    """
    if (
        arrival_at.tzinfo is None
        or requested_at.tzinfo is None
        or arrival_at.utcoffset() is None
        or requested_at.utcoffset() is None
    ):
        raise ValueError(
            "Las fechas deben incluir zona horaria."
        )

    if arrival_at - requested_at >= FREE_CANCELLATION_WINDOW:
        return 0

    return 1
