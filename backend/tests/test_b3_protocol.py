"""Bloque 3B-1: protocolo REAL (interruptor técnico), matriz de endpoints REAL que SIGUE bloqueada,
elegibilidad preparada sin activar y relojes retrospectivos (as_of_at/detected_at)."""
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.ml.predict import PredictionResult
from app.services.processing_protocol import params_of, real_student_processable, require_real_protocol
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo, new_student, measure, evaluate, HIGH  # noqa: F401
from test_s1_schema import assert_sqlstate

ORIGIN = {'Origin': 'http://testserver'}
BLOCKED = 'INSTITUTIONAL_PROCESSING_NOT_READY'


def body(period_id, **changes):
    value = dict(period_id=str(period_id), school_label='Colegio de prueba', cohort_label='3.º secundaria 2026',
        grade_scale_min=0, grade_scale_max=20, participation_min=1, participation_max=5,
        participation_labels={'1': 'Nunca', '5': 'Siempre'},
        bimesters=[dict(code='B1', start_date='2026-03-09', cutoff_date='2026-04-17', cutoff_available_at='2026-04-21T23:59:59-05:00',
                        close_date='2026-05-08', closing_available_at='2026-05-11T12:00:00-05:00', scheduled_days=45),
                   dict(code='B2', start_date='2026-05-18', cutoff_date='2026-06-26', cutoff_available_at='2026-06-30T23:59:59-05:00',
                        close_date='2026-07-17', closing_available_at='2026-07-20T12:00:00-05:00', scheduled_days=45)],
        source_label='Base de prueba', quality_rules={'unique_key': ['student', 'bimester']},
        eligibility_rules=dict(inference_max_missing_fraction=0.4, required_features=['average_grade']),
        risk_rule=dict(version='RIESGO_V1'), opportune_windows=dict(detection_days=3, intervention_days=5))
    value.update(changes)
    return value


def call(state, method, path, payload=None, headers=True):
    sent = {**ORIGIN, 'X-CSRF-Token': state.csrf} if headers is True else (headers or {})
    return getattr(state.client, method)(API + path, **({'json': payload} if payload is not None else {}), headers=sent)


def real_period(state):
    period, section = real_setup(state, 'REAL')
    return period, section


def audit_rows(state, protocol_id):
    with state.owner.connect() as conn:
        return conn.execute(text("""SELECT action,actor_id,recorded_at,payload FROM risk_school.audit_events
            WHERE entity_type='PROCESSING_PROTOCOL' AND entity_id=:id ORDER BY recorded_at,id"""), {'id': protocol_id}).all()


def test_create_is_idempotent_and_rejects_conflicts_and_synthetic_periods(demo):
    state = demo
    period, _ = real_period(state)
    created = call(state, 'post', '/processing-protocols', body(period['id']))
    assert created.status_code == 200, created.text
    protocol = created.json()
    assert protocol['authorization_confirmed_by_admin'] is False and protocol['confirmed_by'] is None and protocol['version'] == 1
    assert protocol['bimesters'][0]['code'] == 'B1' and protocol['grade_scale_max'] == '20.00'
    same = call(state, 'post', '/processing-protocols', body(period['id']))
    assert same.status_code == 200 and same.json()['id'] == protocol['id']
    assert len(audit_rows(state, protocol['id'])) == 1  # PROTOCOL_CREATED una sola vez
    different = call(state, 'post', '/processing-protocols', body(period['id'], school_label='Otro colegio'))
    assert different.status_code == 409 and different.json()['code'] == 'PROTOCOL_EXISTS'
    synthetic = call(state, 'post', '/processing-protocols', body(state.period_id))
    assert synthetic.status_code == 422 and synthetic.json()['code'] == 'PROTOCOL_PERIOD_NOT_REAL'
    outside = call(state, 'post', '/processing-protocols', body(real_period(state)[0]['id'], bimesters=[dict(
        code='B1', start_date='2025-03-09', cutoff_date='2025-04-17', cutoff_available_at='2025-04-21T23:59:59-05:00',
        close_date='2025-05-08', closing_available_at='2025-05-11T12:00:00-05:00', scheduled_days=45)]))
    assert outside.status_code == 422 and outside.json()['code'] == 'PROTOCOL_OUTSIDE_PERIOD'
    for invalid in ({'grade_scale_min': 20}, {'participation_labels': {'9': 'x'}}, {'school_label': ''},
                    {'risk_rule': {'version': 'OTRA'}}, {'consent_documented': True}, {'authorizer': 'x'}):
        response = call(state, 'post', '/processing-protocols', body(real_period(state)[0]['id'], **invalid))
        assert response.status_code == 422, invalid  # tampoco acepta campos de consentimiento/autorizador (extra='forbid')
    assert call(state, 'get', f"/processing-protocols?period_id={period['id']}").json()['id'] == protocol['id']
    assert call(state, 'get', f"/processing-protocols?period_id={uuid4()}").status_code == 404


def test_confirm_revoke_audit_and_immutability(demo):
    state = demo
    period, _ = real_period(state)
    protocol = call(state, 'post', '/processing-protocols', body(period['id'])).json()
    admin = str(state.context['accounts']['ADMIN']['id'])
    confirmed = call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()['authorization_confirmed_by_admin'] is True
    assert confirmed.json()['confirmed_by'] == admin and confirmed.json()['confirmed_at'] and confirmed.json()['version'] == 2
    again = call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm")
    assert again.json()['version'] == 2 and again.json()['confirmed_at'] == confirmed.json()['confirmed_at']  # idempotente
    # Tras confirmar, ningún parámetro se edita (ni siquiera el dueño de la base).
    with state.owner.connect() as conn:
        assert_sqlstate(conn, "UPDATE risk_school.processing_protocols SET school_label='Otro' WHERE id=:id", {'id': protocol['id']}, '55000')
        assert_sqlstate(conn, "UPDATE risk_school.processing_protocols SET confirmed_at=now() WHERE id=:id", {'id': protocol['id']}, '55000')
        assert_sqlstate(conn, 'DELETE FROM risk_school.processing_protocols WHERE id=:id', {'id': protocol['id']}, '55000')
    revoked = call(state, 'post', f"/processing-protocols/{protocol['id']}/revoke")
    assert revoked.status_code == 200 and revoked.json()['authorization_confirmed_by_admin'] is False
    assert revoked.json()['confirmed_by'] is None and revoked.json()['confirmed_at'] is None and revoked.json()['version'] == 3
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/revoke").json()['version'] == 3  # idempotente
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm").json()['version'] == 4  # volver a confirmar
    rows = audit_rows(state, protocol['id'])
    assert [row.action for row in rows] == ['PROTOCOL_CREATED', 'PROTOCOL_AUTHORIZATION_CONFIRMED',
                                            'PROTOCOL_AUTHORIZATION_REVOKED', 'PROTOCOL_AUTHORIZATION_CONFIRMED']
    for row in rows:  # actor + instante UTC; el payload solo lleva identificadores
        assert str(row.actor_id) == admin
        assert row.recorded_at.tzinfo is not None  # instante UTC con zona
        assert set(row.payload) == {'protocol_id', 'period_id'} and row.payload['protocol_id'] == protocol['id']
    serialized = json.dumps([dict(row._mapping, recorded_at=str(row.recorded_at), actor_id=str(row.actor_id)) for row in rows]).lower()
    assert not any(word in serialized for word in ('consent', 'documento', 'autoriz', 'permiso', 'nombre'))
    assert call(state, 'post', f"/processing-protocols/{uuid4()}/confirm").status_code == 404


def test_only_admin_with_csrf_and_origin(demo):
    state = demo
    period, _ = real_period(state)
    protocol = call(state, 'post', '/processing-protocols', body(period['id'])).json()
    for role in ('TUTOR', 'DIRECTOR', 'RESEARCHER'):
        login_as(state, role)
        for method, path, payload in (('post', '/processing-protocols', body(period['id'])),
                                      ('get', f"/processing-protocols?period_id={period['id']}", None),
                                      ('post', f"/processing-protocols/{protocol['id']}/confirm", None),
                                      ('post', f"/processing-protocols/{protocol['id']}/revoke", None)):
            assert call(state, method, path, payload).status_code == 403, (role, path)
    login_as(state, 'ADMIN')
    url = f"/processing-protocols/{protocol['id']}/confirm"
    assert call(state, 'post', url, headers=ORIGIN).status_code == 403                                          # sin CSRF
    assert call(state, 'post', url, headers={'X-CSRF-Token': state.csrf}).status_code == 403                     # sin Origin
    assert call(state, 'post', url, headers={'X-CSRF-Token': state.csrf, 'Origin': 'http://evil.example'}).status_code == 403
    assert call(state, 'get', f"/processing-protocols?period_id={period['id']}").json()['authorization_confirmed_by_admin'] is False
    state.client.cookies.clear()
    assert state.client.get(API + f"/processing-protocols?period_id={period['id']}").status_code == 401
    login_as(state, 'ADMIN')


def test_require_real_protocol_returns_only_confirmed_covering_protocol(demo):
    state = demo
    period, _ = real_period(state)
    protocol = call(state, 'post', '/processing-protocols', body(period['id'])).json()

    def check(expected_ok, period_id=period['id']):
        with state.app.state.database.session_factory() as db:
            from app.models.s1 import AcademicPeriod
            row = db.get(AcademicPeriod, period_id if not isinstance(period_id, str) else __import__('uuid').UUID(period_id))
            if expected_ok:
                assert str(require_real_protocol(db, row).id) == protocol['id']
            else:
                with pytest.raises(AppError) as error:
                    require_real_protocol(db, row)
                assert error.value.status_code == 422 and error.value.code == BLOCKED
    check(False)                                                      # sin confirmar
    call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm")
    check(True)                                                       # confirmado y cubre el periodo
    check(False, state.period_id)                                     # periodo SYNTHETIC: no lo cubre
    other, _ = real_period(state)
    check(False, other['id'])                                         # otro periodo REAL sin protocolo
    call(state, 'post', f"/processing-protocols/{protocol['id']}/revoke")
    check(False)                                                      # revocado


def test_real_endpoints_stay_blocked_even_with_confirmed_protocol(demo):
    state = demo
    period, section = real_period(state)
    student = write(state, '/students', dict(creation_key=str(uuid4()), anon_code='B3R-' + uuid4().hex[:10], full_name='Alumno de Prueba',
                                              period_id=period['id'], section_id=section['id'])).json()
    protocol = call(state, 'post', '/processing-protocols', body(period['id'])).json()
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm").json()['authorization_confirmed_by_admin'] is True
    pid = period['id']
    now = datetime.now(UTC).isoformat()
    attempts = {
        'GET /alerts': call(state, 'get', f'/alerts?period_id={pid}'),
        'POST /alerts/sync': call(state, 'post', '/alerts/sync', {'period_id': pid}),
        'GET /reports/summary': call(state, 'get', f'/reports/summary?period_id={pid}'),
        'GET /reports/export.csv': call(state, 'get', f'/reports/export.csv?period_id={pid}'),
        'GET /indicators': call(state, 'get', f'/indicators?period_id={pid}'),
        'GET /indicators/students': call(state, 'get', f'/indicators/students?period_id={pid}'),
        'GET /indicators/export.csv': call(state, 'get', f'/indicators/export.csv?period_id={pid}'),
        'GET /indicators/interventions.csv': call(state, 'get', f'/indicators/interventions.csv?period_id={pid}'),
        'POST /predictions/run': call(state, 'post', '/predictions/run', {'period_id': pid, 'as_of': now}),
        f"POST /students/{{id}}/evaluate": call(state, 'post', f"/students/{student['id']}/evaluate?period_id={pid}"),
        'POST /imports/preview': state.client.post(API + '/imports/preview', data={'period_id': pid},
            files={'file': ('x.csv', b'student_code\n', 'text/csv')}, headers={'X-CSRF-Token': state.csrf, **ORIGIN}),
    }
    for name, response in attempts.items():
        assert response.status_code == 422 and response.json()['code'] == BLOCKED, (name, response.status_code, response.text[:120])
    # Lo que ya funcionaba con REAL (M1) no cambia: listar estudiantes del periodo REAL sigue permitido.
    assert call(state, 'get', f'/students?period_id={pid}').status_code == 200


def test_real_eligibility_by_confirmed_protocol(demo):
    state = demo
    period, section = real_period(state)
    other_period, other_section = real_period(state)
    mk = lambda p, s: write(state, '/students', dict(creation_key=str(uuid4()), anon_code='B3E-' + uuid4().hex[:10], full_name='Alumno de Prueba',
                                                      period_id=p['id'], section_id=s['id'])).json()
    student, outsider = mk(period, section), mk(other_period, other_section)
    protocol = call(state, 'post', '/processing-protocols', body(period['id'])).json()

    def sql(student_id):
        with state.owner.connect() as conn:
            return (conn.scalar(text('SELECT risk_school.real_student_eligible(:s)'), {'s': student_id}),
                    conn.scalar(text('SELECT risk_school.real_protocol_covers_period(:p)'), {'p': period['id']}))
    assert sql(student['id']) == (False, False)                                    # protocolo sin confirmar
    call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm")
    assert sql(student['id']) == (True, True) and sql(outsider['id'])[0] is False   # solo cubre su propio periodo
    call(state, 'post', f"/processing-protocols/{protocol['id']}/revoke")
    assert sql(student['id']) == (False, False)
    call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm")
    # Activo desde 0008: con protocolo confirmado que cubre su matrícula, el alumno REAL puede marcarse elegible
    # (sin fabricar consentimientos); fuera de un periodo cubierto no.
    with state.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.students SET eligible_for_processing=true WHERE id=:id'), {'id': student['id']})
        flags = conn.execute(text('SELECT eligible_for_processing,consent_documented,assent_documented FROM risk_school.students WHERE id=:id'),
                             {'id': student['id']}).one()
        assert tuple(flags) == (True, False, False)
    with state.owner.connect() as conn:
        assert_sqlstate(conn, 'UPDATE risk_school.students SET eligible_for_processing=true WHERE id=:id', {'id': outsider['id']}, '23514')
    # Regla pura equivalente.
    rule = lambda **c: real_student_processable(**{**dict(data_origin='REAL', is_active=True, eligible_flag=True,
        consent_documented=False, assent_documented=False, protocol_confirmed_for_enrollment=True), **c})
    assert rule() is True and rule(protocol_confirmed_for_enrollment=False) is False
    assert rule(is_active=False) is False and rule(eligible_flag=False) is False
    assert rule(data_origin='SYNTHETIC', protocol_confirmed_for_enrollment=False) is True


def test_retrospective_clocks_default_to_real_instants_and_change_nothing_public(demo, monkeypatch):
    state = demo
    import app.ml.predict as predict
    monkeypatch.setattr(predict, 'predict_snapshot', lambda *a, **k: PredictionResult('EVALUATED', risk_level='HIGH'))
    student = new_student(state)
    measure(state, student, HIGH)
    out = evaluate(state, student).json()
    assert out['status'] == 'EVALUATED' and out['alert_id']
    with state.owner.connect() as conn:
        prediction = conn.execute(text('SELECT as_of_at,predicted_at FROM risk_school.predictions WHERE id=:id'), {'id': out['prediction_id']}).one()
        alert = conn.execute(text('SELECT detected_at,opened_at FROM risk_school.alerts WHERE id=:id'), {'id': out['alert_id']}).one()
        constraints = {row[0] for row in conn.execute(text("SELECT conname FROM pg_constraint WHERE conname IN ('alert_detected_not_after_opened','prediction_as_of_not_after_predicted','study_kind_origin_protocol')"))}
    assert prediction.as_of_at == prediction.predicted_at and alert.detected_at == alert.opened_at   # corridas normales
    assert constraints == {'alert_detected_not_after_opened', 'prediction_as_of_not_after_predicted', 'study_kind_origin_protocol'}
    # Contratos públicos sin campos nuevos.
    detail = state.client.get(API + f"/alerts/{out['alert_id']}").json()
    assert 'detected_at' not in detail['alert'] and 'as_of_at' not in detail['source_prediction']
    assert 'as_of_at' not in state.client.get(API + f"/predictions/{out['prediction_id']}").json()
    # kind/protocolo: los estudios existentes siguen siendo sintéticos y sin protocolo.
    with state.owner.connect() as conn:
        assert conn.execute(text('SELECT DISTINCT kind,data_origin,protocol_id IS NULL FROM risk_school.synthetic_studies')).all() == [('SYNTHETIC_STUDY', 'SYNTHETIC', True)]
        # El estudio institucional queda preparado pero no puede crearse todavía (origen del estudio sigue siendo SYNTHETIC).
        assert_sqlstate(conn, """INSERT INTO risk_school.synthetic_studies(id,period_id,data_origin,generator_version,seed,config,manifest,csv_sha256,
            storage_key,payload_sha256,created_by,kind) VALUES(:id,:p,'SYNTHETIC','synthetic-generator-v1',1,'{}','{}',repeat('a',64),repeat('a',32)||'.json',
            repeat('b',64),:u,'INSTITUTIONAL_STUDY')""", {'id': uuid4(), 'p': state.period_id, 'u': state.context['accounts']['ADMIN']['id']}, '23514')


def test_params_normalization_ignores_numeric_formatting(demo):
    from app.schemas.protocol import ProtocolCreate
    a = ProtocolCreate.model_validate(body(uuid4(), grade_scale_min=0, grade_scale_max=20))
    b = ProtocolCreate.model_validate(body(uuid4(), grade_scale_min='0.00', grade_scale_max='20.0'))
    assert params_of(a) == params_of(b)
