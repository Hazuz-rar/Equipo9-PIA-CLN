"""Pruebas de los endpoints nuevos con personal autenticado y base efímera.

SQLite verifica reglas y transacciones secuenciales, no bloqueos PostgreSQL reales.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db
from src.core.config import settings
from src.core.security import hash_password
from src.infrastructure.database.base import Base
from src.infrastructure.database import models  # noqa: F401
from src.infrastructure.database.models.room_model import RoomModel
from src.infrastructure.database.models.reservation_model import ReservationModel
from src.infrastructure.database.models.staff_model import (
    StaffUserModel, RoomIncidentModel, BusinessAuditModel,
)
from src.infrastructure.database.models.group_model import GroupBookingModel
from src.infrastructure.database.models.exception_model import AvailabilityOutboxModel
from src.domain.rooms.entities import RoomStatus
from src.domain.reservations.entities import ReservationStatus
from src.main import app

ROLES = ('RECEPTION','RESERVATIONS','HOUSEKEEPING','FINANCE','MAINTENANCE',
         'MANAGER_RECEPTION','MANAGER_OPERATIONS')
PASSWORD = 'PassPhrase!_Backend_2030'

@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(settings, 'auth_secret', 't'*64)
    monkeypatch.setattr(settings, 'hotel_timezone', 'America/Mexico_City')
    engine=create_engine('sqlite+pysqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    ids={}
    with Session(engine) as session:
        for role in ROLES:
            staff=StaffUserModel(username=role.lower(),password_hash=hash_password(PASSWORD),role=role,is_active=True)
            session.add(staff)
            session.flush()
            ids[role]=staff.id
        for i in range(1,13):
            session.add(RoomModel(id=uuid4(),number=f'T-{i:03}',room_type='Estándar',
                                  capacity=2,base_rate=Decimal('1000'),status=RoomStatus.AVAILABLE))
        session.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db]=override_db
    try:
        with TestClient(app) as client:
            headers={}
            for role in ROLES:
                response=client.post('/api/v1/auth/token',json={'username':role.lower(),'password':PASSWORD})
                assert response.status_code==200,response.text
                headers[role]={'Authorization':'Bearer '+response.json()['access_token']}
            yield client,engine,headers,ids
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def configure_tariffs(client, headers):
    response=client.post('/api/v1/staff/tariffs/configuration',headers=headers['MANAGER_OPERATIONS'],json={
        'currency':'MXN',
        'bar_by_room_and_season':{'Estándar|alta':'1000'},
        'weekend_multiplier':'1.20',
        'channel_multipliers':{'directo':'1'},
        'customer_multipliers':{'directo':'1'},
        'seasons':[{'name':'alta','start':'2030-12-01','end':'2030-12-31'}],
    })
    assert response.status_code==201,response.text


def seeded_rooms(engine):
    with Session(engine) as session:
        return list(session.scalars(select(RoomModel).order_by(RoomModel.number)))


def create_reservation(client,room_id):
    response=client.post('/api/v1/reservations',json={
        'guest_id':str(uuid4()),'room_id':str(room_id),
        'check_in':'2030-12-10','check_out':'2030-12-13',
    })
    assert response.status_code==201,response.text
    return response.json()['id']


def test_unauthenticated_staff_rejected_and_wrong_role(api):
    client,engine,headers,_=api
    assert client.get('/api/v1/auth/me').status_code in (401,403)
    assert client.get('/api/v1/staff/reports/daily?target_date=2030-12-10').status_code==401
    assert client.get('/api/v1/staff/rooms/dirty',headers=headers['RECEPTION']).status_code==403
    assert client.post('/api/v1/auth/token',json={'username':'reception','password':'wrong'}).status_code==401
    response=client.get('/api/v1/auth/me',headers=headers['HOUSEKEEPING'])
    assert response.status_code==200
    assert response.json()['role']=='HOUSEKEEPING'


def test_tariff_config_roles_and_quote(api):
    client,engine,headers,_=api
    assert client.post('/api/v1/staff/tariffs/configuration',headers=headers['HOUSEKEEPING'],json={}).status_code==403
    configure_tariffs(client,headers)
    response=client.get('/api/v1/staff/tariffs/quote',headers=headers['RESERVATIONS'],params={
        'room_type':'Estándar','check_in':'2030-12-10','check_out':'2030-12-13',
        'channel':'directo','customer_type':'directo',
    })
    assert response.status_code==200,response.text
    assert len(response.json()['nights'])==3
    assert Decimal(str(response.json()['total']))>=Decimal('3000')


def test_reservation_quote_and_cancel_policy(api):
    client,engine,headers,_=api
    configure_tariffs(client,headers)
    rid=create_reservation(client,seeded_rooms(engine)[0].id)
    quoted=client.post(f'/api/v1/staff/tariffs/reservations/{rid}/accept-quote',
                       headers=headers['RESERVATIONS'],json={'channel':'directo','customer_type':'directo','guest_accepted':True})
    assert quoted.status_code==201,quoted.text
    assert Decimal(str(quoted.json()['first_night']))>0
    confirmed=client.patch(f'/api/v1/reservations/{rid}/confirm')
    assert confirmed.status_code==200,confirmed.text
    outbox=client.get('/api/v1/staff/channels/pending',headers=headers['RESERVATIONS'])
    assert outbox.status_code==200 and len(outbox.json())==1
    cancelled=client.post(f'/api/v1/staff/reservations/{rid}/cancel-policy',headers=headers['RESERVATIONS'])
    assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['status']=='CANCELADA'
    assert cancelled.json()['penalty_nights']==0  # Future 2030 date
    assert cancelled.json()['settlement_status']=='NO_CHARGE'
    assert len(client.get('/api/v1/staff/channels/pending',headers=headers['RESERVATIONS']).json())==2
    with Session(engine) as s:
        assert s.get(ReservationModel,uuid4()) is None
        assert s.get(ReservationModel,__import__('uuid').UUID(rid)).status==ReservationStatus.CANCELLED


def test_no_show_rejected_before_arrival(api):
    client,engine,headers,_=api
    rid=create_reservation(client,seeded_rooms(engine)[0].id)
    assert client.patch(f'/api/v1/reservations/{rid}/confirm').status_code==200
    response=client.post(f'/api/v1/staff/reservations/{rid}/no-show',headers=headers['FINANCE'])
    assert response.status_code==409
    assert '23:59' in response.json()['detail']


def test_maintenance_requires_resolution_and_manager(api):
    client,engine,headers,_=api
    room_id=seeded_rooms(engine)[0].id
    registered=client.post(f'/api/v1/staff/rooms/{room_id}/out-of-service',headers=headers['RECEPTION'],json={'reason':'Avería de tubería'})
    assert registered.status_code==201,registered.text
    iid=registered.json()['incident_id']
    assert client.post(f'/api/v1/staff/rooms/{room_id}/restore',headers=headers['RECEPTION'],json={}).status_code==403
    assert client.post(f'/api/v1/staff/rooms/{room_id}/restore',headers=headers['MANAGER_OPERATIONS'],json={}).status_code==409
    assert client.post(f'/api/v1/staff/incidents/{iid}/resolve',headers=headers['MAINTENANCE']).status_code==200
    restored=client.post(f'/api/v1/staff/rooms/{room_id}/restore',headers=headers['MANAGER_OPERATIONS'],json={'requires_cleaning':True})
    assert restored.status_code==200,restored.text
    assert restored.json()['status']=='DIRTY'
    assert client.post(f'/api/v1/staff/rooms/{room_id}/restore',headers=headers['MANAGER_OPERATIONS'],json={}).status_code==409
    with Session(engine) as s:
        assert s.get(RoomModel,room_id).status==RoomStatus.DIRTY
        assert len(list(s.scalars(select(BusinessAuditModel))))>=3


def test_group_block_and_release(api):
    client,engine,headers,_=api
    configure_tariffs(client,headers)
    ids=[str(r.id) for r in seeded_rooms(engine)[:10]]
    response=client.post('/api/v1/staff/groups',headers=headers['RESERVATIONS'],json={
        'organizer':'Grupo de prueba','contract_reference':'Contrato-Demo-2030',
        'room_ids':ids, 'check_in':'2030-12-10','check_out':'2030-12-13',
        'deposit_due_at':'2030-12-01T10:00:00-06:00',
        'channel':'directo','customer_type':'directo',
    })
    assert response.status_code==201,response.text
    gid=response.json()['id']
    assert Decimal(str(response.json()['required_deposit']))>0
    available=client.get('/api/v1/rooms/available',params={
        'check_in':'2030-12-10','check_out':'2030-12-13','guests':1})
    assert available.status_code==200,available.text
    returned_ids={room['id'] for room in available.json()}
    assert not returned_ids.intersection(ids)
    assert len(returned_ids)==2
    assert client.post(f'/api/v1/staff/groups/{gid}/confirm-deposit',headers=headers['RECEPTION'],json={'amount':'99999','receipt_reference':'CompDemo-1'}).status_code==403
    confirmed=client.post(f'/api/v1/staff/groups/{gid}/confirm-deposit',headers=headers['RESERVATIONS'],json={
        'amount':str(response.json()['required_deposit']),'receipt_reference':'Recibo-Manual-Demo-01',
    })
    assert confirmed.status_code==200,confirmed.text
    cancelled=client.post(f'/api/v1/staff/groups/{gid}/cancel',headers=headers['RESERVATIONS'])
    assert cancelled.status_code==200,cancelled.text
    assert len(client.get('/api/v1/rooms/available',params={
        'check_in':'2030-12-10','check_out':'2030-12-13','guests':1}).json())==12


def test_duplicate_warning_and_reporting(api):
    client,engine,headers,_=api
    rooms=seeded_rooms(engine)
    guest=str(uuid4())
    reservation_ids=[]
    for room in rooms[:2]:
        r=client.post('/api/v1/reservations',json={'guest_id':guest,'room_id':str(room.id),
            'check_in':'2030-12-10','check_out':'2030-12-13'})
        assert r.status_code==201
        reservation_ids.append(r.json()['id'])
    duplicates=client.get(f'/api/v1/staff/reservations/{reservation_ids[0]}/possible-duplicates',headers=headers['RESERVATIONS'])
    assert duplicates.status_code==200,duplicates.text
    assert reservation_ids[1] in duplicates.json()['possible_duplicate_ids']
    daily=client.get('/api/v1/staff/reports/daily?target_date=2030-12-10',headers=headers['FINANCE'])
    assert daily.status_code==200,daily.text
    assert len(daily.json()['arrivals'])==2
    weekly=client.get('/api/v1/staff/reports/weekly?start_date=2030-12-09',headers=headers['FINANCE'])
    assert weekly.status_code==200,weekly.text
    assert weekly.json()['adr'] is None


def test_guarantee_rejects_pan_format_and_audit_requires_role(api):
    client,engine,headers,_=api
    rid=create_reservation(client,seeded_rooms(engine)[0].id)
    rejected=client.post(f'/api/v1/staff/reservations/{rid}/guarantee',headers=headers['RECEPTION'],json={
        'method':'Tarjeta','external_reference':'4111111111111111'})
    assert rejected.status_code==409
    accepted=client.post(f'/api/v1/staff/reservations/{rid}/guarantee',headers=headers['RECEPTION'],json={
        'method':'Tarjeta tokenizada','external_reference':'tok_demo_123456'})
    assert accepted.status_code==201,accepted.text
    assert client.get('/api/v1/staff/audit',headers=headers['HOUSEKEEPING']).status_code==403
    assert client.get('/api/v1/staff/audit',headers=headers['MANAGER_RECEPTION']).status_code==200


def test_documentation_check_in_out_all_authenticated(api,monkeypatch):
    from cryptography.fernet import Fernet
    from sqlalchemy.orm import sessionmaker
    import src.api.routes.staff_operations as routes
    client,engine,headers,_=api
    monkeypatch.setattr(settings,'checkin_data_key',Fernet.generate_key().decode('ascii'))
    monkeypatch.setattr(routes,'SessionLocal',sessionmaker(bind=engine))
    room_id=seeded_rooms(engine)[0].id
    rid=create_reservation(client,room_id)
    assert client.patch(f'/api/v1/reservations/{rid}/confirm').status_code==200
    documented=client.post(f'/api/v1/staff/reservations/{rid}/check-in-documentation',
        headers=headers['RECEPTION'],json={
        'full_name':'Huésped demo','official_id_number':'DOC-DEMOSTRACION-01',
        'official_id_valid_until':'2031-01-01',
        'nationality':'Mexicana','contact_details':'Contacto ficticio',
        'invoice_requested':False,'fiscal_address':None,'guarantee_accepted':True,
    })
    assert documented.status_code==200,documented.text
    checked=client.post(f'/api/v1/staff/reservations/{rid}/check-in',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-10T15:30:00-06:00'})
    assert checked.status_code==200,checked.text
    folio_id=checked.json()['folio_id']
    state=client.get(f'/api/v1/staff/folios/{folio_id}',headers=headers['RECEPTION'])
    assert state.status_code==200,state.text
    assert client.get(f'/api/v1/staff/folios/{folio_id}',headers=headers['HOUSEKEEPING']).status_code==403
    completed=client.post(f'/api/v1/staff/reservations/{rid}/check-out',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-13T12:10:00-06:00'})
    assert completed.status_code==200,completed.text
    with Session(engine) as s:
        assert s.get(RoomModel,room_id).status==RoomStatus.DIRTY
        assert s.get(ReservationModel,__import__('uuid').UUID(rid)).status==ReservationStatus.CHECK_OUT
        actions={a.action for a in s.scalars(select(BusinessAuditModel))}
        assert 'CHECK_IN' in actions and 'CHECK_OUT' in actions
    dirty=client.get('/api/v1/staff/rooms/dirty',headers=headers['HOUSEKEEPING'])
    # Nota: la prueba de limpieza en ruta usa un SessionLocal real, por eso
    # no la invocamos aquí; está cubierta por los tests UoW preexistentes.
    assert dirty.status_code==200,dirty.text
    cleaned=client.post(f'/api/v1/staff/rooms/{room_id}/clean',headers=headers['HOUSEKEEPING'])
    assert cleaned.status_code==200,cleaned.text
    assert cleaned.json()['status']=='AVAILABLE'


def test_room_change_during_stay_and_extension(api):
    from uuid import UUID
    from src.infrastructure.database.models.folio_model import FolioModel
    from src.domain.folios.entities import FolioStatus
    client,engine,headers,_=api
    configure_tariffs(client,headers)
    rooms=seeded_rooms(engine)
    rid=create_reservation(client,rooms[0].id)
    quote=client.post(f'/api/v1/staff/tariffs/reservations/{rid}/accept-quote',
                      headers=headers['RESERVATIONS'],json={'channel':'directo','customer_type':'directo','guest_accepted':True})
    assert quote.status_code==201,quote.text
    assert client.patch(f'/api/v1/reservations/{rid}/confirm').status_code==200
    with Session(engine) as s:
        res=s.get(ReservationModel,UUID(rid))
        res.status=ReservationStatus.CHECK_IN
        s.get(RoomModel,rooms[0].id).status=RoomStatus.OCCUPIED
        s.add(FolioModel(id=uuid4(),reservation_id=UUID(rid),status=FolioStatus.OPEN))
        s.commit()
    changed=client.post(f'/api/v1/staff/reservations/{rid}/change-room',headers=headers['RECEPTION'],json={
        'new_room_id':str(rooms[1].id),'reason':'Cambio de habitación solicitado por huésped'})
    assert changed.status_code==200,changed.text
    assert changed.json()['old_room_status']=='DIRTY'
    extended=client.post(f'/api/v1/staff/reservations/{rid}/extend',headers=headers['MANAGER_RECEPTION'],json={
        'new_check_out':'2030-12-15','guest_accepted':True,'reason':'El huésped solicita dos noches más'})
    assert extended.status_code==200,extended.text
    assert extended.json()['new_check_out']=='2030-12-15'
    with Session(engine) as s:
        assert s.get(ReservationModel,UUID(rid)).room_id==rooms[1].id
        assert s.get(RoomModel,rooms[0].id).status==RoomStatus.DIRTY
        assert s.get(RoomModel,rooms[1].id).status==RoomStatus.OCCUPIED


def test_early_checkin_and_late_checkout_with_paid_charge(api, monkeypatch):
    from cryptography.fernet import Fernet
    from sqlalchemy.orm import sessionmaker
    import src.api.routes.staff_operations as routes
    client, engine, headers, _ = api
    monkeypatch.setattr(settings,'checkin_data_key',Fernet.generate_key().decode('ascii'))
    monkeypatch.setattr(routes,'SessionLocal',sessionmaker(bind=engine))
    configure_tariffs(client,headers)
    room_id=seeded_rooms(engine)[0].id
    rid=create_reservation(client,room_id)
    accepted=client.post(f'/api/v1/staff/tariffs/reservations/{rid}/accept-quote',
        headers=headers['RESERVATIONS'],json={'channel':'directo','customer_type':'directo','guest_accepted':True})
    assert accepted.status_code==201
    assert client.patch(f'/api/v1/reservations/{rid}/confirm').status_code==200
    documented=client.post(f'/api/v1/staff/reservations/{rid}/check-in-documentation',
        headers=headers['RECEPTION'],json={
        'full_name':'Huésped ficticio','official_id_number':'DOC-FAKE-88',
        'official_id_valid_until':'2031-12-31','nationality':'Mexicana',
        'contact_details':'Teléfono ficticio','invoice_requested':False,
        'guarantee_accepted':True,
    })
    assert documented.status_code==200,documented.text
    early=client.post(f'/api/v1/staff/reservations/{rid}/check-in',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-10T12:00:00-06:00'})
    assert early.status_code==200,early.text
    folio=early.json()['folio_id']
    unpaid=client.post(f'/api/v1/staff/reservations/{rid}/check-out',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-13T18:01:00-06:00'})
    assert unpaid.status_code==409
    assert 'late check-out' in unpaid.json()['detail']
    charge=client.post(f'/api/v1/staff/reservations/{rid}/late-checkout-charge',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-13T18:01:00-06:00'})
    assert charge.status_code==200,charge.text
    amount=charge.json()['amount']
    assert Decimal(str(amount))>0
    charge_again=client.post(f'/api/v1/staff/reservations/{rid}/late-checkout-charge',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-13T18:01:00-06:00'})
    assert charge_again.status_code==409
    pending=client.post(f'/api/v1/staff/reservations/{rid}/check-out',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-13T18:01:00-06:00'})
    assert pending.status_code==409 and 'saldo pendiente' in pending.json()['detail']
    paid=client.post(f'/api/v1/staff/folios/{folio}/payments',headers=headers['FINANCE'],json={
        'description':'Pago RN-03 demo','amount':str(amount)})
    assert paid.status_code==201,paid.text
    completed=client.post(f'/api/v1/staff/reservations/{rid}/check-out',headers=headers['RECEPTION'],json={
        'simulated_at':'2030-12-13T18:01:00-06:00'})
    assert completed.status_code==200,completed.text


def test_room_inspection_allows_future_availability(api):
    client,engine,headers,_=api
    room_id=seeded_rooms(engine)[0].id
    inspected=client.post(f'/api/v1/staff/rooms/{room_id}/inspect',headers=headers['HOUSEKEEPING'])
    assert inspected.status_code==200,inspected.text
    assert inspected.json()['status']=='INSPECTED'
    listing=client.get('/api/v1/rooms/available',params={'check_in':'2030-12-10','check_out':'2030-12-13','guests':1})
    assert listing.status_code==200
    assert str(room_id) in {r['id'] for r in listing.json()}


def test_walk_requires_partner_evidence_and_manager(api):
    client,engine,headers,_=api
    room=seeded_rooms(engine)[0]
    rid=create_reservation(client,room.id)
    assert client.patch(f'/api/v1/reservations/{rid}/confirm').status_code==200
    with Session(engine) as s:
        s.get(RoomModel,room.id).status=RoomStatus.OUT_OF_ORDER
        s.commit()
    proposal=client.post(f'/api/v1/staff/reservations/{rid}/walk-plan',
        headers=headers['RECEPTION'],json={
        'allied_hotel':'Hotel Aliado Ficticio','transport_details':'Traslado acordado',
        'fare_difference':'250.00','courtesy_details':'Cortesía futura de prueba',
    })
    assert proposal.status_code==201,proposal.text
    walk_id=proposal.json()['walk_id']
    assert client.post(f'/api/v1/staff/walk-cases/{walk_id}/confirm-partner',
        headers=headers['RECEPTION'],json={'partner_booking_reference':'PARTNER-REF-DEMO-1','similar_category_verified':True}).status_code==403
    rejected=client.post(f'/api/v1/staff/walk-cases/{walk_id}/confirm-partner',
        headers=headers['MANAGER_OPERATIONS'],json={
        'partner_booking_reference':'PARTNER-REF-DEMO-1','similar_category_verified':False})
    assert rejected.status_code==409
    confirmed=client.post(f'/api/v1/staff/walk-cases/{walk_id}/confirm-partner',
        headers=headers['MANAGER_OPERATIONS'],json={
        'partner_booking_reference':'PARTNER-REF-DEMO-1','similar_category_verified':True})
    assert confirmed.status_code==200,confirmed.text
    assert confirmed.json()['status']=='REUBICADA'
    with Session(engine) as s:
        assert s.get(ReservationModel,__import__('uuid').UUID(rid)).status==ReservationStatus.RELOCATED
