"""Fixtures ficticios del profesor y los catálogos operativos, sin fechas de estancia inventadas."""
from collections import Counter
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from scripts.import_demo_csv import load_csv_bundle
from scripts.seed_professor_pms import prepare, seed, stable_id
from src.api.dependencies import get_db
from src.core.config import settings
from src.core.security import hash_password
from src.domain.rooms.entities import RoomStatus
from src.infrastructure.database import models  # noqa: F401
from src.infrastructure.database.base import Base
from src.infrastructure.database.models.demo_csv_model import DemoCSVRecordModel
from src.infrastructure.database.models.demo_operational_model import (
    DemoGuestModel, DemoScenarioLineModel, DemoScenarioModel,
)
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.models.staff_model import StaffUserModel
from src.main import app

DATA_ZIP = Path(__file__).resolve().parents[2] / 'data/profesor_fuente/09_Hotel_Costa_Azul.zip'


@pytest.fixture
def session_db():
    engine = create_engine('sqlite+pysqlite://',
        connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for file_rows in load_csv_bundle(DATA_ZIP).values():
            for row in file_rows:
                s.add(DemoCSVRecordModel(**row))
        s.commit()
    yield engine
    engine.dispose()


def test_source_377_converts_to_expected_fixtures(session_db):
    with Session(session_db) as s:
        preview = seed(s)
        assert (preview['huespedes_ficticios'], preview['habitaciones_ficticias']) == (40,20)
        assert (preview['escenarios'],preview['lineas']) == (60,117)
        assert (preview['casos_de_prueba_en_stage'],preview['transiciones_en_stage']) == (120,20)
        assert set(preview['operaciones_sin_detalle']) == {'HOT-O013', 'HOT-O039'}
        assert s.scalar(select(func.count()).select_from(RoomModel)) == 0


def test_requires_explicit_acceptance(session_db):
    with Session(session_db) as s:
        with pytest.raises(ValueError, match='accept-demo-capacities'):
            seed(s, apply=True)
    with Session(session_db) as s:
        assert s.scalar(select(func.count()).select_from(RoomModel)) == 0


def test_seed_and_reseed_preserve_existing_data(session_db):
    with Session(session_db) as s:
        with s.begin():
            s.add(RoomModel(id=uuid4(),number='D-101',room_type='Estándar',
                  capacity=2,base_rate=Decimal('1200'),status=RoomStatus.AVAILABLE))
            result=seed(s,apply=True,confirmed=True)
            assert result['nuevos']=={'guests':40,'rooms':20,'scenarios':60,'lines':117}
    with Session(session_db) as s:
        assert s.scalar(select(func.count()).select_from(RoomModel)) == 21
        assert s.scalar(select(func.count()).select_from(DemoGuestModel)) == 40
        assert s.scalar(select(func.count()).select_from(DemoScenarioModel)) == 60
        assert s.scalar(select(func.count()).select_from(DemoScenarioLineModel)) == 117
        room=s.get(RoomModel,stable_id('room','HOT-P001'))
        assert (room.number, room.room_type, room.capacity, room.base_rate)==('P-001','Estándar',2,Decimal('428'))
        assert s.get(RoomModel,stable_id('room','HOT-P011')).status==RoomStatus.OUT_OF_ORDER
        assert s.scalar(select(RoomModel).where(RoomModel.number=='D-101')).base_rate==Decimal('1200')
        s.get(RoomModel,stable_id('room','HOT-P001')).base_rate=Decimal('999')
        s.commit()
        with s.begin():
            res=seed(s,apply=True,confirmed=True)
            assert res['nuevos']=={}
        assert s.get(RoomModel,stable_id('room','HOT-P001')).base_rate==Decimal('999')
        totals=s.scalars(select(DemoScenarioModel)).all()
        assert sum((x.example_total_mxn for x in totals),Decimal('0'))>0
        assert Counter(x.line_count for x in totals)[0]==2


def test_conflicting_room_name_rolls_back_everything(session_db):
    with Session(session_db) as s:
        with s.begin():
            s.add(RoomModel(id=uuid4(),number='P-001',room_type='Suite',
                  capacity=4,base_rate=Decimal('2000'),status=RoomStatus.AVAILABLE))
        with pytest.raises(ValueError,match='ajena'):
            with s.begin():
                seed(s,apply=True,confirmed=True)
    with Session(session_db) as s:
        assert s.scalar(select(func.count()).select_from(DemoGuestModel)) == 0
        assert s.scalar(select(func.count()).select_from(DemoScenarioModel)) == 0
        assert s.scalar(select(func.count()).select_from(RoomModel)) == 1


def test_auth_required_and_catalog_readable(session_db,monkeypatch):
    with Session(session_db) as s:
        with s.begin():
            seed(s,apply=True,confirmed=True)
        s.add(StaffUserModel(username='gerencia_demo',password_hash=hash_password('PassPhrase_2050!'),
                 role='MANAGER_OPERATIONS',is_active=True))
        s.add(StaffUserModel(username='limpieza_demo',password_hash=hash_password('PassPhrase_2050!'),
                 role='HOUSEKEEPING',is_active=True))
        s.commit()
    monkeypatch.setattr(settings,'auth_secret','T'*64)
    def override_db():
        with Session(session_db) as s:
            yield s
    app.dependency_overrides[get_db]=override_db
    try:
        with TestClient(app) as c:
            assert c.get('/api/v1/staff/demo-data/guests').status_code==401
            admin=c.post('/api/v1/auth/token',json={'username':'gerencia_demo','password':'PassPhrase_2050!'}).json()['access_token']
            hk=c.post('/api/v1/auth/token',json={'username':'limpieza_demo','password':'PassPhrase_2050!'}).json()['access_token']
            assert c.get('/api/v1/staff/demo-data/rooms',headers={'Authorization':f'Bearer {hk}'}).status_code==403
            h={'Authorization':f'Bearer {admin}'}
            guests=c.get('/api/v1/staff/demo-data/guests',headers=h)
            assert guests.status_code==200 and len(guests.json())==40
            rooms=c.get('/api/v1/staff/demo-data/rooms',headers=h)
            assert rooms.status_code==200 and len(rooms.json())==20
            assert 'source_capacity_or_stock' in rooms.json()[0]
            scenarios=c.get('/api/v1/staff/demo-data/scenarios',headers=h)
            assert scenarios.status_code==200 and len(scenarios.json())==60
            detail=c.get('/api/v1/staff/demo-data/scenarios/HOT-O001',headers=h)
            assert detail.status_code==200 and detail.json()['lines']
            assert c.get('/api/v1/staff/demo-data/scenarios/NOEXISTE',headers=h).status_code==404
            assert len(c.get('/api/v1/staff/demo-data/test-cases',headers=h).json())==120
            assert len(c.get('/api/v1/staff/demo-data/transitions',headers=h).json())==20
    finally:
        app.dependency_overrides.clear()
