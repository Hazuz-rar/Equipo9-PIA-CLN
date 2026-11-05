
"""API de folios: consulta para demostración local.

Pendiente: autenticación y autorización para producción.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.dependencies import get_db
from src.api.schemas.folio import FolioResponse
from src.application.folios.services import FolioQueryService
from src.core.config import settings
from src.infrastructure.repositories.sqlalchemy_folio_repository import (
    SQLAlchemyFolioRepository,
)


router = APIRouter()


@router.get(
    "/{folio_id}",
    response_model=FolioResponse,
)
def get_folio(
    folio_id: UUID,
    session: Session = Depends(get_db),
):
    if settings.app_env != "development":
        raise HTTPException(
            status_code=403,
            detail=(
                "Consulta deshabilitada hasta "
                "implementar autenticación."
            ),
        )

    repository = SQLAlchemyFolioRepository(session)
    service = FolioQueryService(repository)

    folio = service.get_by_id(folio_id)

    if folio is None:
        raise HTTPException(
            status_code=404,
            detail="El folio no existe.",
        )

    return FolioResponse.from_domain(folio)
