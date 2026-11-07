"""Inicio de sesión solo para cuentas creadas con scripts/create_staff_user.py."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.core.security import StaffIdentity, current_staff, verify_password, make_access_token
from src.infrastructure.database.models.staff_model import StaffUserModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str

@router.post('/token')
def login(data: LoginRequest, session: Session = Depends(get_db)):
    user = session.scalar(select(StaffUserModel).where(StaffUserModel.username == data.username.strip().lower()))
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Usuario o contraseña incorrectos.')
    try:
        token = make_access_token(user)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail='AUTH_SECRET no está configurada.') from exc
    return {'access_token': token, 'token_type': 'bearer', 'expires_in': 1800}

@router.get('/me')
def who_am_i(actor: StaffIdentity = Depends(current_staff)):
    return {'id':actor.id,'username':actor.username,'role':actor.role}
