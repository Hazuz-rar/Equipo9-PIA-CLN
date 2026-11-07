"""Identificadores deterministas de datos ficticios del profesor."""
from uuid import NAMESPACE_URL, uuid5


def stable_id(kind: str, source_id: str):
    return uuid5(NAMESPACE_URL, f"hotel-costa-azul:csv-profesor:{kind}:{source_id}")
