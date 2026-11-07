"""Autenticación JWT y Argon2. Roles de RN-08, RN-09, RN-10 y US-14/15."""
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from uuid import UUID
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.core.config import settings
from src.infrastructure.database.models.staff_model import StaffUserModel
from src.api.dependencies import get_db

ROLES = frozenset({
    'RECEPTION', 'RESERVATIONS', 'HOUSEKEEPING', 'FINANCE',
    'MAINTENANCE', 'MANAGER_RECEPTION', 'MANAGER_OPERATIONS',
})
MANAGERS = frozenset({'MANAGER_RECEPTION', 'MANAGER_OPERATIONS'})
PH = PasswordHasher()
BEARER = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class StaffIdentity:
    id: UUID
    username: str
    role: str


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError('La contraseña debe tener por lo menos 12 caracteres.')
    return PH.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return PH.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def make_access_token(staff: StaffUserModel) -> str:
    if not settings.auth_secret or len(settings.auth_secret) < 32:
        raise RuntimeError('AUTH_SECRET debe tener al menos 32 caracteres.')
    now = datetime.now(timezone.utc)
    return jwt.encode({
        'sub': str(staff.id), 'iss': 'hotel-costa-azul',
        'aud': 'hotel-costa-azul-api', 'iat': now,
        'exp': now + timedelta(minutes=30),
    }, settings.auth_secret, algorithm='HS256')


def current_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(BEARER),
    session: Session = Depends(get_db),
) -> StaffIdentity:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Autenticación requerida.', headers={'WWW-Authenticate':'Bearer'})
    if not settings.auth_secret or len(settings.auth_secret) < 32:
        raise HTTPException(status_code=503, detail='El servicio de autenticación no está configurado.')
    try:
        payload = jwt.decode(
            credentials.credentials, settings.auth_secret,
            algorithms=['HS256'], audience='hotel-costa-azul-api',
            issuer='hotel-costa-azul', options={'require':['exp','sub','aud','iss']},
        )
        actor_id = UUID(payload['sub'])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail='Credenciales inválidas.', headers={'WWW-Authenticate':'Bearer'}) from exc
    staff = session.get(StaffUserModel, actor_id)
    if staff is None or not staff.is_active or staff.role not in ROLES:
        raise HTTPException(status_code=401, detail='Cuenta inactiva o inexistente.')
    return StaffIdentity(staff.id, staff.username, staff.role)


def require_roles(*allowed: str):
    def guard(staff: StaffIdentity = Depends(current_staff)) -> StaffIdentity:
        if staff.role not in allowed:
            raise HTTPException(status_code=403, detail='Rol sin autorización.')
        return staff
    return guard


def legacy_api_guard(staff_credentials: HTTPAuthorizationCredentials | None = Depends(BEARER), session: Session = Depends(get_db)):
    """Compatibilidad para las pruebas previas: acceso sin token SOLO en desarrollo.

    Nunca desplegar APP_ENV=development en internet.
    """
    if settings.app_env == 'development' and staff_credentials is None:
        return None
    return current_staff(staff_credentials, session)


def legacy_role_guard(*allowed):
    """En producción valida roles; en desarrollo conserva ejemplos Swagger previos."""
    def guard(credentials: HTTPAuthorizationCredentials | None = Depends(BEARER),
              session: Session = Depends(get_db)):
        if settings.app_env == 'development' and credentials is None:
            return None
        actor = current_staff(credentials, session)
        if actor.role not in allowed:
            raise HTTPException(status_code=403,detail='Rol sin autorización.')
        return actor
    return guard
