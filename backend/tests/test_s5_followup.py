"""S5: API real/PostgreSQL riesgo_app y artefactos privados solo en pruebas.

Las clases controladas prueban la política de seguimiento, no eficacia escolar.
El estudio, CSV, comparación y activación existen únicamente en la DB aislada.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import csv
import io
import json
import os
from pathlib import Path
import threading
import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.errors import AppError
from app.models.ml import ModelVersion, PredictionRecord
from app.models.s1 import AppUser, AcademicPeriod
from app.models.s2 import SnapshotRecord
from app.ml.predict import PredictionResult
from app.services import ml, synthetic_study
from test_s1_schema import assert_sqlstate
from test_s3_1_integration import study_env, prepare, import_study, login_as, API

SAMPLES = []


@pytest.fixture(scope='module', autouse=True)
def response_evidence(tmp_path_factory):
    yield
    target = Path('/evidence') if Path('/evidence').exists() else tmp_path_factory.mktemp('s5-evidence')
    prefix = os.environ.get('TEST_REPORT_NAME', 's5-local-backend').removesuffix('-backend')
    (target / (prefix + '-followup-response-samples.json')).write_text(json.dumps(SAMPLES, indent=2)+'\n', encoding='utf-8')


def sample(schema, response):
    SAMPLES.append({'schema': schema, 'body': response.json()})


@pytest.fixture
def followup_env(study_env):
    state = study_env
    prepare(state)
    import_study(state)
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT current_user')) == 'riesgo_app'
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())
        model, _ = synthetic_study.register_model(db, actor, state.settings, state.study_id, None, uuid4())
        synthetic_study.activate_model(db, actor, state.settings, model.id, uuid4())
        state.model_id = model.id
        state.rows = db.execute(text('''SELECT DISTINCT ON(e.id) sn.*,e.student_id,e.section_id,g.tutor_id,s.anon_code
            FROM risk_school.academic_snapshots sn JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
            JOIN risk_school.grade_sections g ON g.id=e.section_id JOIN risk_school.students s ON s.id=e.student_id
            WHERE e.period_id=:period ORDER BY e.id,sn.cutoff_at DESC,sn.revision DESC'''),
            {'period': state.period_id}).mappings().all()
        evaluated = [r for r in state.rows if r['average_grade'] is not None]
        # Control explícito de la clase pública de cada fixture; no se cambia ML.
        state.risks = {r['id']: ('LOW','MEDIUM','HIGH')[index % 3] for index, r in enumerate(evaluated)}
        for row in evaluated:
            ml.persist_evaluated(db, snapshot_id=row['id'], model_id=state.model_id,
                result=PredictionResult('EVALUATED', risk_level=state.risks[row['id']]),
                actor_id=actor.id, request_id=uuid4())
        db.commit()
    return state


def sync(state, *, client=None, csrf=True, period_id=None):
    return (client or state.client).post(API+'/alerts/sync',
        json={'period_id': str(period_id or state.period_id)},
        headers={'X-CSRF-Token': state.csrf} if csrf else {})


def alerts(state, **filters):
    result = state.client.get(API+'/alerts', params={'period_id': str(state.period_id), 'page_size':100, **filters})
    assert result.status_code == 200, result.text
    return result.json()


def detail(state, identifier):
    response = state.client.get(API+f'/alerts/{identifier}')
    assert response.status_code == 200, response.text
    return response.json()


def patch_case(state, case, status, *, version=None, reason=None, client=None):
    data = {'expected_version': case['version'] if version is None else version, 'status': status}
    if reason is not None:
        data['resolution_reason'] = reason
    return (client or state.client).patch(API+f"/alerts/{case['id']}", json=data, headers={'X-CSRF-Token':state.csrf})


def plan(state, case, *, key=None, objective='Actividad exclusivamente simulada S5', client=None, **changes):
    payload = {'alert_id':case['id'], 'expected_alert_version':case['version'],
        'creation_key':str(key or uuid4()), 'kind':'TUTORING', 'objective':objective,
        'scheduled_at':'2027-01-05T14:00:00-05:00', 'notes':'Nota privada de simulación', **changes}
    response = (client or state.client).post(API+'/interventions', json=payload, headers={'X-CSRF-Token':state.csrf})
    return response, payload


def counts(state):
    with state.app.state.database.session_factory() as db:
        return {table:db.scalar(text(f'SELECT count(*) FROM risk_school.{table}'))
            for table in ('alerts','interventions','followup_decisions','predictions','audit_events')}


def correction(state, row, *, risk=None):
    """Una revisión mínima vinculada, solo en PostgreSQL aislado."""
    with state.app.state.database.session_factory() as db:
        source = db.get(SnapshotRecord, row['id'])
        copied = {col.name:getattr(source,col.name) for col in SnapshotRecord.__table__.columns
            if col.name not in ('id','created_at','revision','supersedes_id','row_sha256')}
        new = SnapshotRecord(**copied, revision=source.revision+1, supersedes_id=source.id, row_sha256=uuid4().hex*2)
        db.add(new); db.flush()
        if risk:
            ml.persist_evaluated(db,snapshot_id=new.id,model_id=state.model_id,
                result=PredictionResult('EVALUATED',risk_level=risk),actor_id=state.context['accounts']['ADMIN']['id'],request_id=uuid4())
        db.commit()
        return new.id


def test_policy_existing_predictions_repetition_and_no_fabricated_abstentions(followup_env):
    state=followup_env; before=counts(state)
    response=sync(state); assert response.status_code==200,response.text
    outcome=response.json(); sample('FollowupResult',response)
    required=sum(risk in ('MEDIUM','HIGH') for risk in state.risks.values())
    assert outcome['created']==required and outcome['no_alert']==len(state.risks)-required
    assert outcome['skipped_missing']==len(state.rows)-len(state.risks)
    after=counts(state)
    assert after['alerts']-before['alerts']==required
    assert after['followup_decisions']-before['followup_decisions']==len(state.risks)
    assert after['predictions']==before['predictions']
    cases=alerts(state); assert cases['total']==required
    assert all(c['current_risk_level']==c['severity'] for c in cases['items'])
    response=sync(state); assert response.status_code==200,response.text
    assert response.json()['reused']==len(state.risks) and response.json()['created']==0
    assert counts(state)==after
    response=state.client.get(API+'/alerts',params={'period_id':str(state.period_id),'page_size':5})
    assert response.status_code==200 and len(response.json()['items'])==5
    sample('AlertPage',response)
    response=state.client.get(API+f"/alerts/{cases['items'][0]['id']}")
    sample('AlertDetail',response)
    assert not {'artifact_key','manifest','labels','creation_key','creation_payload_sha256'} & set(json.loads(response.text))


def test_human_transitions_stale_version_terminal_and_same_prediction_not_reopened(followup_env):
    state=followup_env; assert sync(state).status_code==200
    case=alerts(state)['items'][0]
    response=patch_case(state,case,'IN_REVIEW'); assert response.status_code==200,response.text
    reviewed=response.json()['alert']; assert reviewed['version']==case['version']+1
    before=counts(state)
    stale=patch_case(state,case,'RESOLVED',reason='Conclusión exclusivamente simulada')
    assert stale.status_code==409 and counts(state)==before
    no_change=patch_case(state,reviewed,'IN_REVIEW'); assert no_change.status_code==200
    assert no_change.json()['alert']['version']==reviewed['version'] and counts(state)==before
    closed=patch_case(state,reviewed,'RESOLVED',reason='Conclusión exclusivamente simulada')
    assert closed.status_code==200,closed.text
    terminal=closed.json()['alert']; assert terminal['closed_at'] and terminal['version']==reviewed['version']+1
    before=counts(state)
    assert sync(state).json()['created']==0 and counts(state)==before
    assert patch_case(state,terminal,'OPEN').status_code==409
    assert plan(state,terminal)[0].status_code==409
    sample('AlertDetail',closed)


def test_new_revision_pending_low_signal_no_auto_close_and_new_case_after_closure(followup_env):
    state=followup_env; assert sync(state).status_code==200
    case=alerts(state)['items'][0]
    row=next(r for r in state.rows if str(r['enrollment_id'])==case['enrollment_id'])
    prior=detail(state,case['id'])
    historical_as_of=datetime.now(UTC)
    correction(state,row)
    response=sync(state); assert response.status_code==200,response.text
    pending=detail(state,case['id'])
    assert pending['alert']['current_risk_level'] is None
    assert pending['alert']['current_evaluation_status']=='NOT_EVALUATED'
    assert pending['source_prediction']==prior['source_prediction']
    with state.app.state.database.session_factory() as db:
        latest=db.scalar(select(SnapshotRecord).where(SnapshotRecord.enrollment_id==UUID(case['enrollment_id']))
            .order_by(SnapshotRecord.cutoff_at.desc(),SnapshotRecord.revision.desc()))
        ml.persist_evaluated(db,snapshot_id=latest.id,model_id=state.model_id,result=PredictionResult('EVALUATED',risk_level='LOW'),
            actor_id=state.context['accounts']['ADMIN']['id'],request_id=uuid4()); db.commit()
        latest_row={**row,'id':latest.id}
    response=sync(state); assert response.status_code==200,response.text
    assert response.json()['retained_low']==1
    low=detail(state,case['id'])['alert']
    assert low['status']=='OPEN' and low['current_risk_level']=='LOW' and low['severity']==case['severity']
    # as_of anterior reutiliza la revisión histórica, pero nunca devuelve el
    # seguimiento actual a esa fuente ni registra otra decisión del pasado.
    before_historical=counts(state)
    historical=state.client.post(API+'/predictions/run',
        json={'period_id':str(state.period_id),'as_of':historical_as_of.isoformat()},
        headers={'X-CSRF-Token':state.csrf})
    assert historical.status_code==200,historical.text
    sample('PredictionRunResult',historical)
    assert historical.json()['created']==0 and historical.json()['reused']==len(state.risks)
    assert historical.json()['followup']['ignored_stale']==1
    assert historical.json()['followup']['created']==historical.json()['followup']['updated']==0
    assert counts(state)==before_historical
    assert detail(state,case['id'])['alert']==low
    assert detail(state,case['id'])['source_prediction']==prior['source_prediction']
    closed=patch_case(state,low,'DISMISSED',reason='Descartado en simulación'); assert closed.status_code==200
    assert sync(state).json()['created']==0
    correction(state,latest_row,risk='HIGH')
    assert sync(state).json()['created']==1
    new_case=next(c for c in alerts(state)['items'] if c['enrollment_id']==case['enrollment_id'] and c['status']=='OPEN')
    assert new_case['id']!=case['id']
    assert detail(state,case['id'])['alert']['status']=='DISMISSED'


def test_source_update_preserves_human_work_responsible_and_opening(followup_env):
    state=followup_env; sync(state)
    case=alerts(state)['items'][0]
    reviewed=patch_case(state,case,'IN_REVIEW').json()['alert']
    row=next(r for r in state.rows if str(r['enrollment_id'])==case['enrollment_id'])
    correction(state,row,risk='HIGH' if case['severity']=='MEDIUM' else 'MEDIUM')
    result=sync(state); assert result.status_code==200,result.text
    assert result.json()['updated']==1
    updated=detail(state,case['id'])['alert']
    assert updated['status']=='IN_REVIEW' and updated['assigned_to']==reviewed['assigned_to']
    assert updated['opened_at']==reviewed['opened_at'] and updated['version']==reviewed['version']+1
    assert updated['prediction_id']!=reviewed['prediction_id']


@pytest.mark.parametrize('inactive',[False,True])
def test_no_tutor_or_inactive_tutor_never_assigns_administrator(followup_env,inactive):
    state=followup_env
    with state.app.state.database.session_factory() as db:
        if inactive:
            db.execute(text('UPDATE risk_school.app_users SET is_active=false WHERE id=:id'),{'id':state.context['accounts']['TUTOR']['id']})
        else:
            db.execute(text('UPDATE risk_school.grade_sections SET tutor_id=NULL WHERE tutor_id=:id'),{'id':state.context['accounts']['TUTOR']['id']})
        db.commit()
    assert sync(state).status_code==200
    assert all(c['assigned_to'] is None and c['assigned_display_name'] is None for c in alerts(state)['items'])


def test_intervention_original_payload_digest_survives_edits_and_terminal_case(followup_env):
    state=followup_env; sync(state); case=alerts(state)['items'][0]
    created,payload=plan(state,case); assert created.status_code in (200,201),created.text
    sample('InterventionCreateResult',created)
    item=created.json()['intervention']; assert item['status']=='PLANNED' and item['performed_at'] is None
    assert not created.json()['reused_result']
    with state.app.state.database.session_factory() as db:
        original_digest=db.scalar(text('SELECT creation_payload_sha256 FROM risk_school.interventions WHERE id=:id'),{'id':item['id']})
        assert len(original_digest)==64
    before=counts(state)
    repeated=state.client.post(API+'/interventions',json=payload,headers={'X-CSRF-Token':state.csrf})
    assert repeated.status_code==200 and repeated.json()['reused_result'] and repeated.json()['intervention']['id']==item['id']
    assert counts(state)==before
    edited=state.client.patch(API+f"/interventions/{item['id']}",json={'expected_version':item['version'],'objective':'Objetivo editado de simulación'},headers={'X-CSRF-Token':state.csrf})
    assert edited.status_code==200,edited.text
    edited_item=edited.json(); assert edited_item['version']==item['version']+1
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT creation_payload_sha256 FROM risk_school.interventions WHERE id=:id'),{'id':item['id']})==original_digest
    before=counts(state)
    repeated=state.client.post(API+'/interventions',json=payload,headers={'X-CSRF-Token':state.csrf})
    assert repeated.status_code==200 and repeated.json()['reused_result'] and repeated.json()['intervention']['objective']==edited_item['objective']
    conflict=state.client.post(API+'/interventions',json={**payload,'objective':'Intención distinta'},headers={'X-CSRF-Token':state.csrf})
    assert conflict.status_code==409 and counts(state)==before
    stale=state.client.patch(API+f"/interventions/{item['id']}",json={'expected_version':item['version'],'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})
    assert stale.status_code==409 and counts(state)==before
    assert patch_case(state,case,'RESOLVED',reason='Seguimiento concluido solo en simulación').status_code==200
    done=state.client.patch(API+f"/interventions/{item['id']}",json={'expected_version':edited_item['version'],'status':'DONE',
        'performed_at':(datetime.now(UTC)-timedelta(minutes=1)).isoformat(),'notes':'Actividad simulada realizada'},headers={'X-CSRF-Token':state.csrf})
    assert done.status_code==200,done.text
    assert done.json()['performed_at']!=done.json()['scheduled_at'] and done.json()['version']==edited_item['version']+1
    sample('InterventionView',done)
    assert state.client.patch(API+f"/interventions/{item['id']}",json={'expected_version':done.json()['version'],'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf}).status_code==409


@pytest.mark.parametrize('payload',[
    {'expected_version':1,'status':'DONE'},
    {'expected_version':True,'status':'CANCELLED'},
    {'expected_version':'1','status':'CANCELLED'},
    {'expected_version':1,'status':'DONE','performed_at':'2026-10-04T12:00:00'},
    {'expected_version':1,'status':'DONE','performed_at':'2099-01-01T12:00:00Z'},
    {'expected_version':1,'status':'CANCELLED','performed_at':'2025-01-01T12:00:00Z'},
    {'expected_version':1,'origin':'REAL'},
])
def test_invalid_intervention_update_writes_nothing(followup_env,payload):
    state=followup_env; sync(state); case=alerts(state)['items'][0]
    item=plan(state,case)[0].json()['intervention']; before=counts(state)
    response=state.client.patch(API+f"/interventions/{item['id']}",json=payload,headers={'X-CSRF-Token':state.csrf})
    assert response.status_code==422,response.text
    assert counts(state)==before


def test_roles_scope_safe404_csrf_and_real_precedence(followup_env):
    state=followup_env; sync(state); cases=alerts(state)['items']
    own=next(c for c in cases if c['assigned_to']==str(state.context['accounts']['TUTOR']['id']))
    foreign=next(c for c in cases if c['assigned_to'] is None)
    foreign_item=plan(state,foreign)[0].json()['intervention']
    for role in ('TUTOR','DIRECTOR','RESEARCHER'):
        login_as(state,role)
        response=state.client.get(API+'/alerts',params={'period_id':str(state.period_id)})
        assert response.status_code==(403 if role=='RESEARCHER' else 200)
        for route in ('/reports/summary','/reports/export.csv'):
            assert state.client.get(API+route,params={'period_id':str(state.period_id)}).status_code==(403 if role=='RESEARCHER' else 200)
        assert sync(state).status_code==403
        mutation=patch_case(state,own,'IN_REVIEW')
        assert mutation.status_code==(200 if role=='TUTOR' else 403)
        if role=='TUTOR':
            assert plan(state,detail(state,own['id'])['alert'])[0].status_code in (200,201)
        else:
            assert plan(state,own)[0].status_code==403
    login_as(state,'TUTOR')
    missing=state.client.get(API+f'/alerts/{uuid4()}')
    denied=state.client.get(API+f"/alerts/{foreign['id']}")
    assert missing.status_code==denied.status_code==404
    assert {k:v for k,v in missing.json().items() if k!='request_id'}=={k:v for k,v in denied.json().items() if k!='request_id'}
    assert patch_case(state,foreign,'IN_REVIEW').status_code==404
    assert plan(state,foreign)[0].status_code==404
    inaccessible=state.client.patch(API+f"/interventions/{foreign_item['id']}",json={'expected_version':1,'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})
    nonexistent=state.client.patch(API+f'/interventions/{uuid4()}',json={'expected_version':1,'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})
    assert inaccessible.status_code==nonexistent.status_code==404
    assert {k:v for k,v in inaccessible.json().items() if k!='request_id'}=={k:v for k,v in nonexistent.json().items() if k!='request_id'}
    for route in ('/alerts','/reports/summary','/reports/export.csv'):
        assert state.client.get(API+route,params={'period_id':str(state.period_id),'section_id':foreign['section_id']}).status_code==404
    login_as(state,'ADMIN')
    before=counts(state)
    assert sync(state,csrf=False).status_code==403
    assert sync(state,period_id=state.context['periods']['real']['id']).status_code==422
    response=state.client.patch(API+f"/alerts/{own['id']}",json={'expected_version':1,'status':'IN_REVIEW'})
    assert response.status_code==403 and counts(state)==before
    state.client.cookies.clear()
    assert sync(state,period_id=state.context['periods']['real']['id']).status_code==401


def test_locked_period_blocks_all_writes_keeps_reads_and_evidence(followup_env):
    state=followup_env; sync(state); case=alerts(state)['items'][0]
    item=plan(state,case)[0].json()['intervention']
    with state.app.state.database.session_factory() as db:
        db.execute(text('UPDATE risk_school.academic_periods SET is_locked=true WHERE id=:id'),{'id':state.period_id}); db.commit()
    before=counts(state)
    for response in (sync(state),patch_case(state,case,'IN_REVIEW'),plan(state,case)[0],
        state.client.patch(API+f"/interventions/{item['id']}",json={'expected_version':1,'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})):
        assert response.status_code==409 and response.json()['code']=='PERIOD_LOCKED',response.text
    assert counts(state)==before
    assert state.client.get(API+f"/alerts/{case['id']}").status_code==200
    assert state.client.get(API+'/reports/summary',params={'period_id':str(state.period_id)}).status_code==200
    with state.app.state.database.session_factory() as db:
        assert_sqlstate(db,"DELETE FROM risk_school.alerts WHERE id=:id",{'id':case['id']},'42501')
        assert_sqlstate(db,"UPDATE risk_school.followup_decisions SET decision=decision WHERE prediction_id=:id",{'id':case['prediction_id']},'42501')


def test_database_incompatible_links_unique_active_case_and_owner_immutability(followup_env):
    state=followup_env; sync(state); cases=alerts(state)['items']
    case,foreign=cases[:2]
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT current_user'))=='riesgo_app'
        savepoint=db.begin_nested()
        try:
            with pytest.raises(DBAPIError) as error:
                db.execute(text('UPDATE risk_school.alerts SET prediction_id=:prediction,version=version+1 WHERE id=:id'),
                    {'prediction':foreign['prediction_id'],'id':case['id']})
            assert error.value.orig.sqlstate in ('23503','23514')
        finally:
            savepoint.rollback()
        assert_sqlstate(db,"INSERT INTO risk_school.alerts(enrollment_id,prediction_id,data_origin,severity) VALUES(:enrollment,:prediction,'SYNTHETIC',:severity)",
            {'enrollment':case['enrollment_id'],'prediction':case['prediction_id'],'severity':case['severity']},'23505')
    with state.owner.connect() as owner:
        assert_sqlstate(owner,'UPDATE risk_school.followup_decisions SET decision=decision WHERE prediction_id=:id',{'id':case['prediction_id']},'55000')
        assert_sqlstate(owner,'DELETE FROM risk_school.followup_decisions WHERE prediction_id=:id',{'id':case['prediction_id']},'55000')
        assert_sqlstate(owner,'DELETE FROM risk_school.alerts WHERE id=:id',{'id':case['id']},'55000')


def test_no_active_model_preserves_case_history_and_reports_without_invented_low(followup_env):
    state=followup_env; sync(state); case=alerts(state)['items'][0]
    with state.app.state.database.session_factory() as db:
        model=db.get(ModelVersion,state.model_id);model.is_active=False;db.commit()
    before=counts(state)
    response=sync(state); assert response.status_code==409 and response.json()['code']=='MODEL_NOT_AVAILABLE'
    assert counts(state)==before
    selected=detail(state,case['id'])
    assert selected['latest_prediction'] is None and selected['source_prediction']
    assert selected['alert']['current_risk_level'] is None and selected['alert']['current_evaluation_status']=='NOT_EVALUATED'
    summary=state.client.get(API+'/reports/summary',params={'period_id':str(state.period_id)}).json()
    assert summary['evaluations']=={'evaluated':0,'not_evaluated':len(state.rows),'insufficient_data':0}
    assert all(v['count']==0 and v['percentage'] is None for v in summary['risks'].values())


def test_unregistered_same_year_section_cannot_sync_or_expose_followup(followup_env):
    state=followup_env
    from app.services import followup
    selected=next(row for row in state.rows if state.risks.get(row['id']) in ('MEDIUM','HIGH'))
    with state.app.state.database.session_factory() as db:
        actor=db.get(AppUser,state.context['accounts']['ADMIN']['id'])
        prediction=db.scalar(select(PredictionRecord).where(PredictionRecord.snapshot_id==selected['id'],PredictionRecord.model_id==state.model_id))
        result=followup.sync_current(db,actor,state.period_id,state.settings,uuid4(),prediction_ids=[prediction.id])
        assert result.created==1;db.commit()
    case=alerts(state)['items'][0]
    foreign=uuid4()
    with state.app.state.database.session_factory() as db:
        grade=db.scalar(text('SELECT grade FROM risk_school.grade_sections WHERE id=:id'),{'id':selected['section_id']})
        db.execute(text("INSERT INTO risk_school.academic_periods(code,school_year,start_date,end_date,data_origin) VALUES(:code,:year,:start,:end,'REAL')"),
            {'code':'S5-REAL-'+uuid4().hex[:12],'year':state.config.school_year,'start':state.config.period_start,'end':state.config.period_end})
        db.execute(text('INSERT INTO risk_school.grade_sections(id,code,grade,school_year) VALUES(:id,:code,:grade,:year)'),
            {'id':foreign,'code':'S5-FOREIGN-'+uuid4().hex[:12],'grade':grade,'year':state.config.school_year})
        # Corrupción exclusiva de fixture: misma matrícula/origen/año, sección
        # ajena al manifest. No se crea ni se mueve una cuenta o dato activo.
        db.execute(text('UPDATE risk_school.enrollments SET section_id=:section WHERE id=:id'),
            {'section':foreign,'id':selected['enrollment_id']});db.commit()
    before=counts(state)
    response=sync(state)
    assert response.status_code==409 and response.json()['code']=='STUDY_INTEGRITY_ERROR',response.text
    assert counts(state)==before
    listed=alerts(state);assert listed['total']==0
    report=state.client.get(API+'/reports/summary',params={'period_id':str(state.period_id),'page_size':100})
    assert report.status_code==200,report.text
    assert report.json()['total']==len(state.rows)-1
    assert str(selected['enrollment_id']) not in {row['enrollment_id'] for row in report.json()['items']}
    assert state.client.get(API+f"/alerts/{case['id']}").status_code==404
    assert patch_case(state,case,'IN_REVIEW').status_code==404


def test_summary_full_denominators_multiple_cases_interventions_csv_and_timeline(followup_env):
    state=followup_env; sync(state); case=alerts(state)['items'][0]
    first=plan(state,case)[0].json()['intervention']
    second=plan(state,case,objective='Segunda actividad de prueba')[0].json()['intervention']
    done=state.client.patch(API+f"/interventions/{first['id']}",json={'expected_version':1,'status':'DONE',
        'performed_at':(datetime.now(UTC)-timedelta(minutes=1)).isoformat()},headers={'X-CSRF-Token':state.csrf})
    cancelled=state.client.patch(API+f"/interventions/{second['id']}",json={'expected_version':1,'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})
    assert done.status_code==cancelled.status_code==200
    assert patch_case(state,case,'RESOLVED',reason='Cierre de simulación para comprobar historia').status_code==200
    row=next(r for r in state.rows if str(r['enrollment_id'])==case['enrollment_id'])
    correction(state,row,risk='HIGH'); sync(state)
    response=state.client.get(API+'/reports/summary',params={'period_id':str(state.period_id),'page_size':5})
    assert response.status_code==200,response.text
    report=response.json(); sample('ReportSummary',response)
    assert report['total']==len(state.rows) and len(report['items'])==5
    assert report['total']==sum(report['evaluations'].values())
    assert report['evaluations']['evaluated']==sum(v['count'] for v in report['risks'].values())
    assert all(v['denominator']==report['evaluations']['evaluated'] for v in report['risks'].values())
    assert report['interventions']=={'planned':0,'done':1,'cancelled':1}
    assert report['cases']['resolved']==1
    response=state.client.get(API+'/reports/export.csv',params={'period_id':str(state.period_id)})
    assert response.status_code==200 and response.headers['content-type'].startswith('text/csv')
    assert response.headers['cache-control']=='no-store' and 'attachment' in response.headers['content-disposition']
    assert response.content.startswith(b'\xef\xbb\xbf')
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert len(rows)==report['total']
    assert len({r['codigo_sintetico'] for r in rows})==len(rows)
    assert not any(s in response.text for s in ('Nota privada','Cierre de simulación','artifact_key','password_hash'))
    filtered=state.client.get(API+'/reports/summary',params={'period_id':str(state.period_id),'alert_status':'RESOLVED','page_size':100})
    assert filtered.status_code==200 and filtered.json()['total']==1,filtered.text
    filtered_csv=state.client.get(API+'/reports/export.csv',params={'period_id':str(state.period_id),'alert_status':'RESOLVED'})
    filtered_rows=list(csv.DictReader(io.StringIO(filtered_csv.content.decode('utf-8-sig'))))
    assert [r['codigo_sintetico'] for r in filtered_rows]==[r['anon_code'] for r in filtered.json()['items']]
    timeline=state.client.get(API+f"/students/{case['student_id']}/timeline",params={'period_id':str(state.period_id),'page_size':100})
    assert timeline.status_code==200,timeline.text
    events=timeline.json()['items']; assert len({e['id'] for e in events})==len(events)
    assert sum(e['entity_id']==case['id'] and e['summary']=='Apertura de alerta' for e in events)==1
    assert any(e['event_type']=='INTERVENTION' and 'realizada' in e['summary'] for e in events)
    assert any(e['event_type']=='INTERVENTION' and 'cancelada' in e['summary'] for e in events)
    sample('TimelineEventPage',timeline)
    no_rows=state.client.get(API+'/reports/summary',params={'period_id':str(state.period_id),'search':'NO-MATCH'})
    assert no_rows.status_code==200 and no_rows.json()['total']==0
    assert all(value['percentage'] is None and value['reason'] for value in no_rows.json()['risks'].values())


@pytest.mark.parametrize('value',[ '=1+1','\t+SUM(1;2)','\r@cmd','\n-42','  =FORMULA()','Sección "A", José ñ'])
def test_csv_formula_controls_quoting_unicode_preserves_database(followup_env,value):
    state=followup_env
    section=state.rows[0]['section_id'];student=state.rows[0]['student_id']
    with state.app.state.database.session_factory() as db:
        db.execute(text('UPDATE risk_school.students SET anon_code=:code WHERE id=:id'),{'code':value,'id':student});db.commit()
    response=state.client.get(API+'/reports/export.csv',params={'period_id':str(state.period_id),'section_id':str(section)})
    assert response.status_code==200,response.text
    rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig')))); assert rows
    # Ninguna celda evaluable conserva el prefijo de fórmula tras controles/espacios.
    for row in rows:
        for cell in row.values():
            assert not cell.lstrip(' \t\r\n').startswith(('=','+','-','@'))
    cleaned=value.replace('\t','').replace('\r','').replace('\n','')
    expected=cleaned if 'José' in value else "'"+cleaned
    assert any(r['codigo_sintetico']==expected for r in rows)
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT anon_code FROM risk_school.students WHERE id=:id'),{'id':student})==value


def test_sync_rollback_and_inference_followup_rollback_share_transaction(followup_env,monkeypatch):
    state=followup_env
    from app.services import followup
    original=followup.sync_current
    def fail_after_followup(*args,**kwargs):
        original(*args,**kwargs)
        raise AppError(409,'S5_ROLLBACK_PROBE','Fallo exclusivo de prueba tras seguimiento.')
    monkeypatch.setattr(followup,'sync_current',fail_after_followup)
    before=counts(state)
    response=sync(state); assert response.status_code==409,response.text
    assert counts(state)==before
    correction(state,next(r for r in state.rows if r['average_grade'] is not None))
    before=counts(state)
    response=state.client.post(API+'/predictions/run',json={'period_id':str(state.period_id),'as_of':datetime.now(UTC).isoformat()},headers={'X-CSRF-Token':state.csrf})
    assert response.status_code==409,response.text
    assert counts(state)==before
    monkeypatch.setattr(followup,'sync_current',original)
    response=state.client.post(API+'/predictions/run',json={'period_id':str(state.period_id),'as_of':datetime.now(UTC).isoformat()},headers={'X-CSRF-Token':state.csrf})
    assert response.status_code==200,response.text
    assert response.json()['created']==1 and response.json()['followup']['created']>0
    sample('PredictionRunResult',response)


def test_followup_mutation_and_audit_failures_roll_back_together(followup_env,monkeypatch):
    state=followup_env;sync(state);case=alerts(state)['items'][0]
    item=plan(state,case)[0].json()['intervention']
    from app.services import followup
    original=followup.event
    def reject_after_audit(*args,**kwargs):
        original(*args,**kwargs)
        raise AppError(409,'S5_AUDIT_ROLLBACK_PROBE','Fallo exclusivo de prueba después de auditar.')
    monkeypatch.setattr(followup,'event',reject_after_audit)
    before=counts(state)
    for response in (patch_case(state,case,'IN_REVIEW'),plan(state,case)[0],
        state.client.patch(API+f"/interventions/{item['id']}",json={'expected_version':1,'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})):
        assert response.status_code==409 and response.json()['code']=='S5_AUDIT_ROLLBACK_PROBE',response.text
        assert counts(state)==before
    record=detail(state,case['id'])
    assert record['alert']['status']=='OPEN' and record['alert']['version']==case['version']
    assert record['interventions'][0]['status']=='PLANNED' and record['interventions'][0]['version']==1


def test_concurrent_sync_and_human_edits_no_duplicate_no_lost_work(followup_env):
    state=followup_env
    clients=[TestClient(state.app,cookies=state.client.cookies) for _ in range(2)]
    gate=threading.Barrier(2)
    def worker(client):
        gate.wait(timeout=10); return sync(state,client=client)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=[future.result(timeout=30) for future in [pool.submit(worker,c) for c in clients]]
        assert all(r.status_code==200 for r in replies),[r.text for r in replies]
        required=sum(r in ('MEDIUM','HIGH') for r in state.risks.values())
        assert sum(r.json()['created'] for r in replies)==required
        with state.app.state.database.session_factory() as db:
            assert db.scalar(text('SELECT count(*) FROM risk_school.followup_decisions WHERE study_id=:id'),{'id':state.study_id})==len(state.risks)
        case=alerts(state)['items'][0]
        gate=threading.Barrier(2)
        def edit(client):
            gate.wait(timeout=10); return patch_case(state,case,'IN_REVIEW',client=client)
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=[f.result(timeout=30) for f in [pool.submit(edit,c) for c in clients]]
        assert sorted(r.status_code for r in replies)==[200,409]
        assert detail(state,case['id'])['alert']['version']==case['version']+1
        gate=threading.Barrier(2);key=uuid4()
        payload={'alert_id':case['id'],'expected_alert_version':case['version']+1,
            'creation_key':str(key),'kind':'TUTORING','objective':'Planificación concurrente exclusivamente simulada',
            'scheduled_at':'2027-01-05T14:00:00-05:00','notes':None}
        def simultaneous_plan(client):
            gate.wait(timeout=10)
            return client.post(API+'/interventions',json=payload,headers={'X-CSRF-Token':state.csrf})
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=[future.result(timeout=30) for future in [pool.submit(simultaneous_plan,c) for c in clients]]
        assert sorted(response.status_code for response in replies)==[200,201]
        assert sorted(response.json()['reused_result'] for response in replies)==[False,True]
        assert replies[0].json()['intervention']['id']==replies[1].json()['intervention']['id']
        with state.app.state.database.session_factory() as db:
            identifier=replies[0].json()['intervention']['id']
            assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='INTERVENTION_CREATED'"),{'id':identifier})==1
    finally:
        for client in clients:client.close()


@pytest.mark.parametrize('concurrent_operation',['inference','edit'])
def test_sync_exclusion_observed_by_db_with_inference_or_human_edit(followup_env,monkeypatch,concurrent_operation):
    state=followup_env;sync(state);case=alerts(state)['items'][0]
    reviewed=patch_case(state,case,'IN_REVIEW').json()['alert']
    row=next(r for r in state.rows if str(r['enrollment_id'])==case['enrollment_id'])
    correction(state,row,risk='HIGH' if case['severity']=='MEDIUM' else 'MEDIUM')
    from app.repositories import followup as repository
    original=repository.lock_enrollments
    held,release=threading.Event(),threading.Event()
    latch=threading.Lock();first={'pending':True};sync_pid={}
    def controlled_lock(db,*args,**kwargs):
        rows=original(db,*args,**kwargs)
        with latch:
            should_hold=first['pending'];first['pending']=False
        if should_hold:
            sync_pid['value']=db.scalar(text('SELECT pg_backend_pid()'))
            held.set();assert release.wait(15),'No se liberó la coordinación de prueba'
        return rows
    monkeypatch.setattr(repository,'lock_enrollments',controlled_lock)
    clients=[TestClient(state.app,cookies=state.client.cookies) for _ in range(2)]
    def other_write():
        if concurrent_operation=='edit':
            return patch_case(state,reviewed,'RESOLVED',reason='Intención simulada concurrente',client=clients[1])
        return clients[1].post(API+'/predictions/run',json={'period_id':str(state.period_id),'as_of':datetime.now(UTC).isoformat()},headers={'X-CSRF-Token':state.csrf})
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            syncing=executor.submit(sync,state,client=clients[0]);assert held.wait(10)
            waiting=executor.submit(other_write)
            try:
                deadline=time.monotonic()+10;observed=False
                with state.owner.connect() as observer:
                    while time.monotonic()<deadline:
                        observer.execute(text('SELECT pg_stat_clear_snapshot()'))
                        observed=observer.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE :pid=ANY(pg_blocking_pids(pid)))'),{'pid':sync_pid['value']})
                        if observed:break
                assert observed,'La operación concurrente no esperó el lock real de matrícula'
                assert not waiting.done()
            finally:
                release.set()
            sync_response=syncing.result(timeout=20);other_response=waiting.result(timeout=30)
        assert sync_response.status_code==200 and sync_response.json()['updated']==1,sync_response.text
        if concurrent_operation=='edit':
            assert other_response.status_code==409,other_response.text
        else:
            assert other_response.status_code==200 and other_response.json()['created']==0,other_response.text
        final=detail(state,case['id'])['alert']
        assert final['status']=='IN_REVIEW' and final['version']==reviewed['version']+1
    finally:
        release.set()
        for client in clients:client.close()


@pytest.mark.parametrize('operation',['sync','case','intervention','inference'])
def test_period_closure_observed_db_lock_blocks_each_write_then_rejects(followup_env,operation):
    state=followup_env
    assert sync(state).status_code==200
    case=alerts(state)['items'][0]
    item=plan(state,case)[0].json()['intervention']
    # El evento coordina el comienzo; pg_blocking_pids prueba la espera real.
    started=threading.Event(); client=TestClient(state.app,cookies=state.client.cookies)
    before=counts(state)
    def syncing():
        started.set()
        if operation=='case':
            return patch_case(state,case,'IN_REVIEW',client=client)
        if operation=='intervention':
            return client.patch(API+f"/interventions/{item['id']}",json={'expected_version':1,'status':'CANCELLED'},headers={'X-CSRF-Token':state.csrf})
        if operation=='inference':
            return client.post(API+'/predictions/run',json={'period_id':str(state.period_id),'as_of':datetime.now(UTC).isoformat()},headers={'X-CSRF-Token':state.csrf})
        return sync(state,client=client)
    try:
        with state.app.state.database.session_factory() as locker:
            assert locker.scalar(text('SELECT current_user'))=='riesgo_app'
            pid=locker.scalar(text('SELECT pg_backend_pid()'))
            locker.execute(text('UPDATE risk_school.academic_periods SET is_locked=true WHERE id=:id'),{'id':state.period_id})
            with ThreadPoolExecutor(max_workers=1) as pool:
                waiting=pool.submit(syncing)
                try:
                    assert started.wait(10)
                    deadline=time.monotonic()+10; observed=False
                    with state.owner.connect() as observer:
                        while time.monotonic()<deadline:
                            observer.execute(text('SELECT pg_stat_clear_snapshot()'))
                            observed=observer.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE :pid=ANY(pg_blocking_pids(pid)))'),{'pid':pid})
                            if observed:break
                    assert observed,'No se observó la petición esperando el lock real del periodo'
                    assert not waiting.done()
                finally:
                    # Liberar ANTES de ThreadPool.__exit__, también si falla una
                    # aserción: el cierre del pool espera a la petición bloqueada.
                    locker.commit()
                response=waiting.result(timeout=20)
                assert response.status_code==409 and response.json()['code']=='PERIOD_LOCKED',response.text
        assert counts(state)==before
    finally:
        client.close()
