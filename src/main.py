
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.routes.demo_data import router as demo_data_router
from src.api.routes.health import router as health_router
from src.api.routes.auth import router as auth_router
from src.api.routes.staff_operations import router as staff_operations_router
from src.api.routes.tariffs import router as tariffs_router
from src.api.routes.exceptions import router as exceptions_router
from src.api.routes.reports import router as reports_router
from src.api.routes.groups import router as groups_router
from src.api.routes.room_changes import router as room_changes_router
from src.api.routes.walk import router as walk_router
from src.core.security import legacy_api_guard
from fastapi import Depends
from src.api.routes.reservations import router as reservations_router
from src.api.routes.folios import router as folios_router
from src.api.routes.rooms import router as rooms_router
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

security = HTTPBasic()

# Define aquí el usuario y contraseña que se pedirán para ver el Swagger
SWAGGER_USER = "admin"
SWAGGER_PASSWORD = "admin1234567" # Puedes cambiarla por la que prefieras

def verify_swagger_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    is_username_correct = secrets.compare_digest(credentials.username, SWAGGER_USER)
    is_password_correct = secrets.compare_digest(credentials.password, SWAGGER_PASSWORD)
    
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas para acceder a la documentación",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

if settings.app_env == 'production' and (
    len(settings.auth_secret) < 32 or not settings.checkin_data_key or not settings.hotel_timezone
):
    raise RuntimeError(
        'Producción requiere AUTH_SECRET (>=32 caracteres), '
        'CHECKIN_DATA_KEY y HOTEL_TIMEZONE.'
    )

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API REST del sistema PMS del Hotel Costa Azul.",
    docs_url=None,   # Desactivamos la ruta por defecto
    redoc_url=None,  # Desactivamos la ruta por defecto
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    demo_data_router,
    prefix=f"{settings.api_v1_prefix}/staff/demo-data",
    tags=["Datos del profesor"],
)
app.include_router(auth_router, prefix=f"{settings.api_v1_prefix}/auth", tags=["Authentication"])
app.include_router(staff_operations_router, prefix=f"{settings.api_v1_prefix}/staff", tags=["Staff Operations"])
app.include_router(tariffs_router, prefix=f"{settings.api_v1_prefix}/staff/tariffs", tags=["Tariffs"])
app.include_router(exceptions_router, prefix=f"{settings.api_v1_prefix}/staff", tags=["Exception Policies"])
app.include_router(reports_router, prefix=f"{settings.api_v1_prefix}/staff/reports", tags=["Reports"])
app.include_router(groups_router, prefix=f"{settings.api_v1_prefix}/staff/groups", tags=["Group Reservations"])
app.include_router(room_changes_router, prefix=f"{settings.api_v1_prefix}/staff/reservations", tags=["Stay Changes"])
app.include_router(walk_router, prefix=f"{settings.api_v1_prefix}/staff", tags=["Overbooking / Walk"])

app.include_router(
    health_router,
    prefix=settings.api_v1_prefix,
    tags=["Health"],
)

app.include_router(
    reservations_router,
    prefix=f"{settings.api_v1_prefix}/reservations",
    tags=["Reservations"],
    dependencies=[Depends(legacy_api_guard)],
)


app.include_router(
    folios_router,
    prefix=f"{settings.api_v1_prefix}/folios",
    tags=["Folios"],
)


app.include_router(
    rooms_router,
    prefix=f"{settings.api_v1_prefix}/rooms",
    tags=["Rooms"],
)


@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "message": "Hotel Costa Azul API",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health",
    }

@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html(username: str = Depends(verify_swagger_credentials)):
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=f"{settings.app_name} - Swagger UI")

@app.get("/redoc", include_in_schema=False)
def redoc_html(username: str = Depends(verify_swagger_credentials)):
    return get_redoc_html(openapi_url=app.openapi_url, title=f"{settings.app_name} - ReDoc")
