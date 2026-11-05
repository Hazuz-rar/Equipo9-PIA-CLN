from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Verificar estado de la API")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "hotel-costa-azul-api"}
