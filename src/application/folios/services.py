
"""Consultas de Folio: ADR-002, ADR-004 y ADR-005."""

from typing import Protocol
from uuid import UUID

from src.domain.folios.entities import Folio
from src.domain.folios.value_objects import FolioId


class FolioReader(Protocol):
    def get_by_id(
        self, folio_id: FolioId
    ) -> Folio | None:
        ...


class FolioQueryService:
    def __init__(
        self,
        repository: FolioReader,
    ) -> None:
        self.repository = repository

    def get_by_id(
        self,
        folio_id: UUID,
    ) -> Folio | None:
        return self.repository.get_by_id(
            FolioId(folio_id)
        )
