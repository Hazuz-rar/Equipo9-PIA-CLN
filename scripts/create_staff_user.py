"""Uso: python scripts/create_staff_user.py --username recepcion01 --role RECEPTION
Solicita la contraseña ocultándola. Nunca crear cuentas mediante una ruta anónima.
"""
import argparse
import sys
from pathlib import Path
from getpass import getpass
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import select
from src.core.security import ROLES, hash_password
from src.infrastructure.database.session import SessionLocal
from src.infrastructure.database.models.staff_model import StaffUserModel

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', required=True)
    parser.add_argument('--role', required=True, choices=sorted(ROLES))
    args = parser.parse_args()
    name = args.username.strip().lower()
    if not name:
        parser.error('Nombre de usuario obligatorio.')
    password = getpass('Contraseña (mínimo 12 caracteres): ')
    with SessionLocal() as session:
        if session.scalar(select(StaffUserModel.id).where(StaffUserModel.username == name)):
            parser.error('Ese usuario ya existe.')
        session.add(StaffUserModel(username=name, password_hash=hash_password(password), role=args.role, is_active=True))
        session.commit()
    print('Cuenta creada; la contraseña no se imprimió.')

if __name__ == '__main__':
    main()
