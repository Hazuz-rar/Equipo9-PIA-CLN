
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class ReservationCreate(BaseModel):
    guest_id: UUID
    room_id: UUID
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("La fecha de salida debe ser posterior a la entrada.")
        return self


class ReservationResponse(BaseModel):
    id: UUID
    guest_id: UUID
    room_id: UUID
    check_in: date
    check_out: date
    status: str

    model_config = ConfigDict(from_attributes=True)

class CancellationPreviewResponse(BaseModel):
    reservation_id: UUID
    penalty_nights: int
    message: str = (
        "Vista previa: no se canceló la reserva "
        "ni se registraron cobros."
    )
