
from fastapi import FastAPI

from src.core.config import settings
from src.api.routes.health import router as health_router
from src.api.routes.reservations import (
    router as reservations_router,
)
from src.api.routes.folios import (
    router as folios_router,
)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API REST del sistema PMS del Hotel Costa Azul.",
)


app.include_router(
    health_router,
    prefix=settings.api_v1_prefix,
    tags=["Health"],
)

app.include_router(
    reservations_router,
    prefix=f"{settings.api_v1_prefix}/reservations",
    tags=["Reservations"],
)

app.include_router(
    folios_router,
    prefix=f"{settings.api_v1_prefix}/folios",
    tags=["Folios"],
)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "message": "Hotel Costa Azul API",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }
