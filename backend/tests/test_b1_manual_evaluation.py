"""Bloque 1: medición manual → evaluación → caso, solo en simulación SYNTHETIC.

DB y artefactos aislados. Las clases forzadas prueban la política de seguimiento,
no eficacia escolar ni datos del colegio.
"""
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.ml.predict import PredictionResult
from app.models.s1 import AppUser
from app.services import synthetic_study
from test_s1_schema import assert_sqlstate
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia: no contamina bootstrap/S1)

ORIGIN = {'Origin': 'http://testserver'}
HIGH = dict(average_grade=7, attendance_pct=50, activities_pct=40, participation_level=1, behavior_incidents=8)
LOW = dict(average_grade=18, attendance_pct=98, activities_pct=95, participation_level=3, behavior_incidents=0)


@pytest.fixture
def demo(study_env):
    state = study_env
    prepare(state)
    import_study(state)
    with state.app.state.database.session_factory() as db:
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())
        model, _ = synthetic_study.register_model(db, actor, state.settings, state.study_id, None, uuid4())
        synthetic_study.activate_model(db, actor, state.settings, model.id, uuid4())
        state.model_id = model.id
    with state.owner.connect() as conn:
        state.section_id = conn.scalar(text('SELECT section_id FROM risk_school.enrollments WHERE period_id=:p LIMIT 1'),
                                       {'p': state.period_id})
    return state


def post(state, path, body=None, client=None):
    return (client or state.client).post(API + path, json=body, headers={**ORIGIN, 'X-CSRF-Token': state.csrf})


def new_student(state, **extra):
    body = dict(creation_key=str(uuid4()), anon_code='B1-' + uuid4().hex[:10], full_name='Alumno de Prueba',
                period_id=str(state.period_id), section_id=str(state.section_id), **extra)
    response = post(state, '/students', body)
    assert response.status_code == 200, response.text
    return response.json()


def measure(state, student, values=None, **extra):
    body = dict(creation_key=str(uuid4()), window_start='2025-03-16', cutoff_at='2025-04-15T18:00:00-05:00',
                available_at='2025-04-15T17:00:00-05:00', purpose='PARTIAL', **(values or HIGH), **extra)
    response = post(state, f"/students/{student['id']}/measurements?period_id={state.period_id}", body)
    assert response.status_code == 200, response.text
    return response.json()


def evaluate(state, student, period_id=None, client=None):
    return post(state, f"/students/{student['id']}/evaluate?period_id={period_id or state.period_id}", client=client)


def alert_count(state, enrollment_id):
    with state.owner.connect() as conn:
        return conn.scalar(text("SELECT count(*) FROM risk_school.alerts WHERE enrollment_id=:e AND status IN ('OPEN','IN_REVIEW')"),
                           {'e': enrollment_id})


def enrollment_of(state, student):
    with state.owner.connect() as conn:
        return conn.scalar(text('SELECT id FROM risk_school.enrollments WHERE student_id=:s AND period_id=:p'),
                           {'s': student['id'], 'p': state.period_id})


def test_manual_student_is_eligible_only_in_synthetic(demo):
    state = demo
    student = new_student(state)
    with state.owner.connect() as conn:
        flags = conn.execute(text('SELECT eligible_for_processing,consent_documented,assent_documented FROM risk_school.students WHERE id=:s'),
                             {'s': student['id']}).one()
    assert tuple(flags) == (True, False, False)
    period, section = real_setup(state, 'REAL')
    body = dict(creation_key=str(uuid4()), anon_code='B1R-' + uuid4().hex[:10], full_name='Alumno de Prueba',
                period_id=period['id'], section_id=section['id'])
    real = write(state, '/students', body)
    assert real.status_code == 200, real.text
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT eligible_for_processing FROM risk_school.students WHERE id=:s'), {'s': real.json()['id']}) is False


def test_migration_0006_in_clean_database_keeps_real_blocked(database_urls):
    owner = make_url(database_urls[1])
    name = 'riesgo_escolar_test_b1_mig_' + uuid4().hex[:12]
    engine = create_engine(owner, isolation_level='AUTOCOMMIT', hide_parameters=True)
    with engine.connect() as db:
        db.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        db.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        db.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    engine.dispose()
    environment = {**os.environ, 'MIGRATION_DATABASE_URL': owner.set(database=name).render_as_string(hide_password=False)}
    environment.pop('MIGRATION_DATABASE_URL_FILE', None)
    result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
                            env=environment, capture_output=True)
    assert result.returncode == 0, 'Isolated 0006 upgrade failed'
    engine = create_engine(owner.set(database=name), hide_parameters=True)
    with engine.connect() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version')) in ('0006_manual_evaluable', '0007_real_protocol', '0008_real_chain')
        body = db.scalar(text("SELECT prosrc FROM pg_proc WHERE proname='deny_manual_prediction'"))
        assert "'SYNTHETIC'" in body and 'requires a SYNTHETIC period and model' in body
        assert db.scalar(text("SELECT has_function_privilege('riesgo_app','risk_school.deny_manual_prediction()','EXECUTE')"))
        assert not db.scalar(text("SELECT has_function_privilege('public','risk_school.deny_manual_prediction()','EXECUTE')"))
        assert db.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgname='m1_prediction_guard'")) == 1
    engine.dispose()


def test_trigger_still_blocks_manual_prediction_on_real(demo):
    state = demo
    period, section = real_setup(state, 'REAL')
    body = dict(creation_key=str(uuid4()), anon_code='B1T-' + uuid4().hex[:10], full_name='Alumno de Prueba',
                period_id=period['id'], section_id=section['id'])
    student = write(state, '/students', body).json()
    values = dict(creation_key=str(uuid4()), window_start='2026-04-01', cutoff_at='2026-05-01T18:00:00-05:00',
                  available_at='2026-05-01T17:00:00-05:00', purpose='PARTIAL', **LOW)
    snapshot = write(state, f"/students/{student['id']}/measurements?period_id={period['id']}", values).json()
    with state.owner.connect() as conn:
        enrollment = conn.scalar(text('SELECT id FROM risk_school.enrollments WHERE student_id=:s'), {'s': student['id']})
        with pytest.raises(Exception) as error:
            conn.execute(text("""INSERT INTO risk_school.predictions(id,enrollment_id,snapshot_id,model_id,data_origin,risk_level,
                probabilities_calibrated) VALUES(:id,:e,:sn,:m,'REAL','LOW',false)"""),
                {'id': uuid4(), 'e': enrollment, 'sn': snapshot['id'], 'm': state.model_id})
        assert 'requires a SYNTHETIC period and model' in str(error.value)


def test_evaluates_manual_measurement_without_storing_target_date(demo):
    state = demo
    student = new_student(state)
    snapshot = measure(state, student)
    response = evaluate(state, student)
    assert response.status_code == 200, response.text
    out = response.json()
    assert out['status'] == 'EVALUATED' and out['risk_level'] in ('LOW', 'MEDIUM', 'HIGH')
    assert out['snapshot_id'] == snapshot['id'] and out['prediction_reused'] is False
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT target_date FROM risk_school.academic_snapshots WHERE id=:i'), {'i': snapshot['id']}) is None
        assert conn.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE action='STUDENT_EVALUATION_REQUESTED' AND entity_id=:e"),
                           {'e': enrollment_of(state, student)}) == 1
    detail = state.client.get(API + f"/students/{student['id']}?period_id={state.period_id}").json()
    assert detail['latest_prediction']['risk_level'] == out['risk_level']
    assert detail['student']['evaluation_status'] == 'EVALUATED'
    prediction = detail['latest_prediction']
    assert prediction['target_date'] is None
    assert prediction['model_horizon_date'] == '2025-04-29'  # corte 2025-04-15 Lima + 14 días del modelo


def test_missing_required_variable_gives_insufficient_data_without_risk(demo):
    state = demo
    student = new_student(state)
    measure(state, student, {**HIGH, 'average_grade': None})
    out = evaluate(state, student).json()
    assert out['status'] == 'INSUFFICIENT_DATA' and out['risk_level'] is None and out['prediction_id'] is None
    detail = state.client.get(API + f"/students/{student['id']}?period_id={state.period_id}").json()
    assert detail['latest_prediction'] is None and detail['student']['risk_level'] is None
    assert detail['student']['evaluation_status'] == 'INSUFFICIENT_DATA'
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.predictions WHERE enrollment_id=:e'),
                           {'e': enrollment_of(state, student)}) == 0


def test_value_outside_model_scale_gets_clear_error_and_no_prediction(demo):
    state = demo
    student = new_student(state)
    measure(state, student, {**LOW, 'participation_level': 5})  # el modelo sintético admite categorías 1–3
    response = evaluate(state, student)
    assert response.status_code == 422 and response.json()['code'] == 'MEASUREMENT_OUT_OF_MODEL_SCALE'
    assert 'participación' in response.json()['message']
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.predictions WHERE enrollment_id=:e'),
                           {'e': enrollment_of(state, student)}) == 0


def test_without_measurement_is_a_clear_error(demo):
    student = new_student(demo)
    response = evaluate(demo, student)
    assert response.status_code == 422 and response.json()['code'] == 'NO_MEASUREMENT'


def test_real_period_is_still_blocked(demo):
    state = demo
    period, section = real_setup(state, 'REAL')
    body = dict(creation_key=str(uuid4()), anon_code='B1P-' + uuid4().hex[:10], full_name='Alumno de Prueba',
                period_id=period['id'], section_id=section['id'])
    student = write(state, '/students', body).json()
    values = dict(creation_key=str(uuid4()), window_start='2026-04-01', cutoff_at='2026-05-01T18:00:00-05:00',
                  available_at='2026-05-01T17:00:00-05:00', purpose='PARTIAL', **LOW)
    assert write(state, f"/students/{student['id']}/measurements?period_id={period['id']}", values).status_code == 200
    response = evaluate(state, student, period_id=period['id'])
    assert response.status_code == 422 and response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.predictions p JOIN risk_school.enrollments e ON e.id=p.enrollment_id WHERE e.period_id=:p'),
                           {'p': period['id']}) == 0


@pytest.mark.parametrize('risk,expect_case', [('HIGH', True), ('MEDIUM', True), ('LOW', False)])
def test_followup_policy_creates_case_only_for_medium_high(demo, monkeypatch, risk, expect_case):
    state = demo
    import app.ml.predict as predict
    monkeypatch.setattr(predict, 'predict_snapshot', lambda *a, **k: PredictionResult('EVALUATED', risk_level=risk))
    student = new_student(state)
    measure(state, student)
    out = evaluate(state, student).json()
    enrollment = enrollment_of(state, student)
    assert out['risk_level'] == risk
    if expect_case:
        assert out['case_action'] == 'CREATED' and out['alert_id']
        case = state.client.get(API + f"/alerts/{out['alert_id']}").json()['alert']
        assert case['severity'] == risk and case['status'] == 'OPEN'
        assert alert_count(state, enrollment) == 1
    else:
        assert out['case_action'] == 'NONE' and out['alert_id'] is None
        assert alert_count(state, enrollment) == 0
    # Idempotente: misma medición y modelo reutilizan predicción y decisión.
    again = evaluate(state, student).json()
    assert again['prediction_id'] == out['prediction_id'] and again['prediction_reused'] is True
    assert again['alert_id'] == out['alert_id']
    assert again['case_action'] == ('REUSED' if expect_case else 'NONE')
    assert alert_count(state, enrollment) == (1 if expect_case else 0)


def test_revision_invalidates_prior_prediction_and_keeps_single_active_case(demo, monkeypatch):
    state = demo
    import app.ml.predict as predict
    risks = iter(['MEDIUM', 'HIGH'])
    monkeypatch.setattr(predict, 'predict_snapshot', lambda *a, **k: PredictionResult('EVALUATED', risk_level=next(risks)))
    student = new_student(state)
    first_snapshot = measure(state, student)
    first = evaluate(state, student).json()
    enrollment = enrollment_of(state, student)
    revised = measure(state, student, {**HIGH, 'average_grade': 6}, supersedes_id=first_snapshot['id'], expected_revision=1,
                      correction_reason='Corrección de digitación')
    detail = state.client.get(API + f"/students/{student['id']}?period_id={state.period_id}").json()
    # La predicción anterior pertenece a la revisión previa: no se muestra ni se reutiliza.
    assert detail['latest_prediction'] is None and detail['student']['risk_level'] is None
    second = evaluate(state, student).json()
    assert second['snapshot_id'] == revised['id'] and second['prediction_id'] != first['prediction_id']
    assert second['prediction_reused'] is False and second['risk_level'] == 'HIGH'
    assert second['alert_id'] == first['alert_id'] and second['case_action'] == 'UPDATED'
    assert alert_count(state, enrollment) == 1
    case = state.client.get(API + f"/alerts/{second['alert_id']}").json()['alert']
    assert case['severity'] == 'HIGH' and case['version'] == 2


@pytest.mark.parametrize('role', ['TUTOR', 'DIRECTOR', 'RESEARCHER'])
def test_only_admin_can_evaluate(demo, role):
    state = demo
    student = new_student(state)
    measure(state, student)
    login_as(state, role)
    response = evaluate(state, student)
    assert response.status_code == 403, response.text
    login_as(state, 'ADMIN')
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.predictions WHERE enrollment_id=:e'),
                           {'e': enrollment_of(state, student)}) == 0


def test_evaluate_requires_csrf_and_origin(demo):
    state = demo
    student = new_student(state)
    measure(state, student)
    url = API + f"/students/{student['id']}/evaluate?period_id={state.period_id}"
    assert state.client.post(url, headers=ORIGIN).status_code == 403
    assert state.client.post(url, headers={'X-CSRF-Token': state.csrf, 'Origin': 'http://evil.example'}).status_code == 403
    assert state.client.post(url, headers={'X-CSRF-Token': state.csrf}).status_code == 403


def test_locked_period_rejects_evaluation(demo):
    state = demo
    student = new_student(state)
    measure(state, student)
    with state.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.academic_periods SET is_locked=true WHERE id=:p'), {'p': state.period_id})
    try:
        response = evaluate(state, student)
        assert response.status_code == 409 and response.json()['code'] == 'PERIOD_LOCKED'
    finally:
        with state.owner.begin() as conn:
            conn.execute(text('UPDATE risk_school.academic_periods SET is_locked=false WHERE id=:p'), {'p': state.period_id})
