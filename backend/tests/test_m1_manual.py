"""API real y PostgreSQL migrado; altas exclusivas de la DB test aislada."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient
from test_s2_imports import env, login_as, preview, commit, row, assert_preview
from conftest import database_urls as _database_urls
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
import os
import subprocess
import sys


@pytest.fixture(scope='module')
def database_urls(_database_urls):
    """M1 prueba ambos orígenes sin contaminar los supuestos de fixtures S1."""
    name='riesgo_escolar_test_m1_'+uuid4().hex[:12]
    owner=make_url(_database_urls[1])
    engine=create_engine(owner,isolation_level='AUTOCOMMIT',hide_parameters=True)
    with engine.connect() as db:
        db.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        db.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        db.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    engine.dispose()
    urls=tuple(make_url(url).set(database=name).render_as_string(hide_password=False) for url in _database_urls)
    environment={**os.environ,'MIGRATION_DATABASE_URL':urls[1]}
    environment.pop('MIGRATION_DATABASE_URL_FILE',None)
    result=subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],env=environment,capture_output=True)
    assert result.returncode==0,'M1 isolated migration failed'
    return urls


@pytest.fixture(scope='module')
def owner_engine(database_urls):
    engine=create_engine(database_urls[1],hide_parameters=True)
    yield engine
    engine.dispose()

API='/api/v1'


def write(env,path,body,method='post'):
    return getattr(env.client,method)(API+path,json=body,headers={'Origin':'http://testserver','X-CSRF-Token':env.csrf})


def setup(env,origin='REAL'):
    p=write(env,'/periods',dict(creation_key=str(uuid4()),code='M1-'+uuid4().hex[:8],school_year=2026,
        start_date='2026-01-01',end_date='2026-12-31',data_origin=origin))
    assert p.status_code==200,p.text
    g=write(env,'/sections',dict(creation_key=str(uuid4()),code='M1-'+uuid4().hex[:8],grade=1,school_year=2026,
        tutor_id=str(env.context['accounts']['TUTOR']['id']),data_origin=origin))
    assert g.status_code==200,g.text
    return p.json(),g.json()


def student(env,p,g,**values):
    body=dict(creation_key=str(uuid4()),anon_code='M1-'+uuid4().hex[:10],full_name='Álvaro de Prueba',period_id=p['id'],section_id=g['id'])
    body.update(values)
    return body,write(env,'/students',body)


def measurement(**values):
    return dict(creation_key=str(uuid4()),window_start='2026-04-01',cutoff_at='2026-05-01T18:00:00-05:00',
        available_at='2026-05-01T17:00:00-05:00',purpose='PARTIAL',average_grade=0,attendance_pct=None,
        activities_pct=90,participation_level=5,behavior_incidents=0,**values)


def path(s,p):
    return f"/students/{s['id']}/measurements?period_id={p['id']}"


def test_m1_atomic_persistence_revision_inactive_audit(env):
    p,g=setup(env)
    body,response=student(env,p,g,anon_code='  m1   '+uuid4().hex[:12]+'  ')
    assert response.status_code==200,response.text
    s=response.json()
    assert s['anon_code']==body['anon_code'].strip().upper().replace('   ',' ')
    assert write(env,'/students',body).json()==s
    assert student(env,p,g,anon_code=s['anon_code'])[1].status_code==409
    m=measurement()
    result=write(env,path(s,p),m)
    assert result.status_code==200,result.text
    first=result.json()
    assert first['target_date'] is None and first['created_by']==str(env.context['accounts']['ADMIN']['id'])
    assert first['average_grade']==0 and first['attendance_pct'] is None and first['revision']==1
    assert write(env,path(s,p),m).json()==first
    changed={**m,'average_grade':1}
    assert write(env,path(s,p),changed).status_code==409
    revision={**m,'creation_key':str(uuid4()),'average_grade':12,'supersedes_id':first['id'],
        'expected_revision':1,'correction_reason':'Corrección de digitación'}
    second=write(env,path(s,p),revision)
    assert second.status_code==200,second.text
    assert second.json()['revision']==2 and second.json()['supersedes_id']==first['id']
    assert write(env,path(s,p),{**revision,'creation_key':str(uuid4())}).status_code==409
    detail=env.client.get(API+f"/students/{s['id']}?period_id={p['id']}").json()
    assert detail['student']['risk_level'] is None and detail['latest_prediction'] is None
    assert detail['student']['full_name']==s['full_name']
    patch=dict(creation_key=str(uuid4()),expected_version=1,full_name=s['full_name'],is_active=False,confirmed=True,reason='Baja solicitada')
    assert write(env,f"/students/{s['id']}",patch,'patch').status_code==200
    assert write(env,path(s,p),{**m,'creation_key':str(uuid4())}).status_code==409
    history=env.client.get(API+path(s,p)).json()
    assert history['total']==2
    assert write(env,f"/students/{s['id']}",{**patch,'creation_key':str(uuid4()),'is_active':True},'patch').status_code==409
    assert write(env,f"/students/{s['id']}",{**patch,'creation_key':str(uuid4()),'expected_version':2,'is_active':True},'patch').status_code==200
    with env.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action=\'M1_MEASUREMENT_CREATED\''),{'id':first['id']})==1
        raw=conn.execute(text('SELECT import_batch_id,source_row_number,row_sha256 FROM risk_school.academic_snapshots WHERE id=:id'),{'id':first['id']}).one()
        assert tuple(raw)==(None,None,None)
        flags=conn.execute(text('SELECT eligible_for_processing,consent_documented,assent_documented FROM risk_school.students WHERE id=:id'),{'id':s['id']}).one()
        assert tuple(flags)==(False,False,False)


@pytest.mark.parametrize('field,value', [('average_grade',20.01),('average_grade',-1),('attendance_pct',101),('activities_pct',-1),
    ('participation_level',0),('participation_level',6),('participation_level',2.5),('behavior_incidents',-1),
    ('behavior_incidents',True),('average_grade','12'),('average_grade',True),('cutoff_at','2026-05-01T12:00:00'),
    ('cutoff_at','2026-05-01T12:00:00Z'),('window_start','2025-12-30')])
def test_m1_strict_validation(env,field,value):
    p,g=setup(env)
    _,s=student(env,p,g)
    body=measurement()
    body[field]=value
    assert write(env,path(s.json(),p),body).status_code==422


def test_m1_empty_invalid_dates_availability_and_origin(env):
    p,g=setup(env,'SYNTHETIC')
    _,s=student(env,p,g)
    assert s.status_code==200,s.text
    body=measurement()
    for key in ('average_grade','attendance_pct','activities_pct','participation_level','behavior_incidents'):
        body[key]=None
    assert write(env,path(s.json(),p),body).status_code==422
    body=measurement(variable_available_at={'average_grade':'2026-05-01T17:30:00-05:00'})
    assert write(env,path(s.json(),p),body).status_code==422
    real,_=setup(env)
    request=dict(creation_key=str(uuid4()),student_id=s.json()['id'],period_id=real['id'],section_id=g['id'])
    assert write(env,'/enrollments',request).status_code==404


def test_m1_catalog_duplicates_tutor_lock_atomic_and_enrollment(env):
    p,g=setup(env)
    bad=dict(creation_key=str(uuid4()),code='X',grade=1,school_year=2026,tutor_id=str(env.context['accounts']['DIRECTOR']['id']),data_origin='REAL')
    assert write(env,'/sections',bad).status_code==422
    assert write(env,'/sections',{**bad,'code':g['code'],'tutor_id':g['tutor_id']}).status_code==409
    body,r=student(env,p,g,section_id=str(uuid4()))
    assert r.status_code==404
    assert env.client.get(API+'/student-identities',params={'search':body['anon_code']}).json()==[]
    body,r=student(env,p,g)
    s=r.json()
    enrollment=env.client.get(API+f"/students/{s['id']}?period_id={p['id']}").json()['student']
    assert write(env,'/enrollments',dict(creation_key=str(uuid4()),student_id=s['id'],period_id=p['id'],section_id=g['id'])).status_code==409
    m=write(env,path(s,p),measurement())
    assert m.status_code==200,m.text
    _,other=setup(env)
    assert write(env,f"/enrollments/{enrollment['enrollment_id']}",dict(creation_key=str(uuid4()),section_id=other['id'],expected_version=1),'patch').status_code==409
    lock={k:p[k] for k in ('code','school_year','start_date','end_date','data_origin')}
    lock.update(creation_key=str(uuid4()),is_locked=True,expected_version=1)
    assert write(env,f"/periods/{p['id']}",lock,'patch').status_code==200
    assert student(env,p,g)[1].status_code==409
    assert write(env,path(s,p),measurement()).status_code==409
    assert write(env,f"/periods/{p['id']}",{**lock,'creation_key':str(uuid4()),'is_locked':False},'patch').status_code==409


@pytest.mark.parametrize('role',['TUTOR','DIRECTOR','RESEARCHER'])
def test_m1_direct_permissions_safe_404(env,role):
    p,g=setup(env)
    _,r=student(env,p,g)
    s=r.json()
    # Otra sección sin el tutor de prueba, conservando su rol activo.
    with env.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.grade_sections SET tutor_id=NULL WHERE id=:id'),{'id':g['id']})
    login_as(env,role)
    assert student(env,p,g)[1].status_code==403
    read=env.client.get(API+f"/students/{s['id']}?period_id={p['id']}")
    assert read.status_code==({'TUTOR':404,'DIRECTOR':200,'RESEARCHER':403}[role])
    denied=write(env,path(s,p),measurement())
    assert denied.status_code==({'TUTOR':404,'DIRECTOR':403,'RESEARCHER':403}[role])
    if role=='TUTOR':
        with env.owner.begin() as conn:
            conn.execute(text('UPDATE risk_school.grade_sections SET tutor_id=:t WHERE id=:id'),{'id':g['id'],'t':env.context['accounts']['TUTOR']['id']})
        assert write(env,path(s,p),measurement()).status_code==200


def test_m1_csrf_origin_csv_compatibility(env):
    p,g=setup(env)
    body,_=student(env,p,g)
    assert env.client.post(API+'/students',json={**body,'creation_key':str(uuid4())}).status_code==403
    assert env.client.post(API+'/students',json=body,headers={'X-CSRF-Token':env.csrf,'Origin':'https://alien.invalid'}).status_code==403
    # Gate de importación de producción intacto; fixture histórica habilita solo su CSV controlado.
    batch=assert_preview(preview(env))
    result=commit(env,batch)
    assert result.status_code==200,result.text


def test_m1_concurrent_idempotency_and_revision_conflict(env):
    p,g=setup(env)
    body=dict(creation_key=str(uuid4()),anon_code='M1-CONCURRENT-'+uuid4().hex[:8],full_name='Prueba concurrente',period_id=p['id'],section_id=g['id'])
    cookie=env.client.cookies.get('session')
    headers={'Origin':'http://testserver','X-CSRF-Token':env.csrf,'Cookie':'session='+cookie}
    def send_student(_):
        with TestClient(env.app) as client:
            return client.post(API+'/students',json=body,headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(send_student,range(2)))
    assert [r.status_code for r in results]==[200,200]
    assert results[0].json()['id']==results[1].json()['id']
    s=results[0].json()
    first=write(env,path(s,p),measurement()).json()
    base=measurement()
    base.update(supersedes_id=first['id'],expected_revision=1,correction_reason='Prueba simultánea')
    def revise(_):
        with TestClient(env.app) as client:
            return client.post(API+path(s,p),json={**base,'creation_key':str(uuid4())},headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(revise,range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    assert env.client.get(API+path(s,p)).json()['total']==2


def test_m1_audit_failure_rolls_back_identity_and_enrollment(env,monkeypatch):
    from app.services import manual
    from sqlalchemy.exc import SQLAlchemyError
    p,g=setup(env)
    def fail_audit(**kwargs):
        raise SQLAlchemyError('injected isolated audit failure')
    monkeypatch.setattr(manual,'AuditEvent',fail_audit)
    body,result=student(env,p,g)
    assert result.status_code==503
    with env.owner.connect() as db:
        assert db.scalar(text('SELECT count(*) FROM risk_school.students WHERE anon_code=:code'),{'code':body['anon_code']})==0
