
"""Persistencia de registro de check-in cifrado con Fernet.

El secreto se recibe por configuración, no está en el código ni en BD.
"""

import json
from datetime import date, datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from src.domain.reception.check_in import (
    GuestCheckInRegistration,
)
from src.infrastructure.database.models.check_in_model import (
    CheckInRecordModel,
)


class SQLAlchemyCheckInRepository:
    def __init__(
        self,
        session: Session,
        encryption_key: str,
    ):
        self.session = session
        self.cipher = Fernet(encryption_key.encode("ascii"))

    def add(
        self,
        reservation_id: UUID,
        record: GuestCheckInRegistration,
    ) -> None:
        data = {
            "full_name": record.full_name,
            "official_id_number": record.official_id_number,
            "official_id_valid_until": (
                record.official_id_valid_until.isoformat()
            ),
            "nationality": record.nationality,
            "contact_details": record.contact_details,
            "invoice_requested": record.invoice_requested,
            "fiscal_address": record.fiscal_address,
            "guarantee_accepted": record.guarantee_accepted,
            "registered_at": record.registered_at.isoformat(),
        }

        token = self.cipher.encrypt(
            json.dumps(
                data,
                ensure_ascii=False,
            ).encode("utf-8")
        )

        self.session.add(
            CheckInRecordModel(
                reservation_id=reservation_id,
                encrypted_payload=token,
                registered_at=record.registered_at.astimezone(
                    timezone.utc
                ),
                guarantee_accepted=record.guarantee_accepted,
                missing_guarantee_risk=record.missing_guarantee_risk,
            )
        )

        self.session.flush()

    def get_by_reservation_id(
        self,
        reservation_id: UUID,
    ) -> GuestCheckInRegistration | None:

        model = self.session.get(
            CheckInRecordModel,
            reservation_id,
        )

        if model is None:
            return None

        data = json.loads(
            self.cipher.decrypt(model.encrypted_payload)
        )

        return GuestCheckInRegistration(
            full_name=data["full_name"],
            official_id_number=data["official_id_number"],
            official_id_valid_until=date.fromisoformat(
                data["official_id_valid_until"]
            ),
            nationality=data["nationality"],
            contact_details=data["contact_details"],
            invoice_requested=data["invoice_requested"],
            fiscal_address=data["fiscal_address"],
            guarantee_accepted=data["guarantee_accepted"],
            registered_at=datetime.fromisoformat(
                data["registered_at"]
            ),
        )
