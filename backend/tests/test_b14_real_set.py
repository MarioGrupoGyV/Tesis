"""Bloque 10 (ADR 015): consulta de solo lectura del conjunto real y su cierre. Datos ficticios etiquetados REAL."""
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text

from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo  # noqa: F401
from test_b3_protocol import call
from test_b4_real_cycle import BIMESTERS, STUDENTS
from test_b12_demo_copy import real_cycle, real_counts


def audit_count(state):
    with state.owner.connect() as conn:
        return conn.scalar(text('SELECT count(*) FROM risk_school.audit_events'))


def test_real_set_is_read_only_scoped_and_locks_the_period(demo):
    state = demo
    period, model_id, _, _ = real_cycle(state)
    for spec in BIMESTERS.values():
        as_of = datetime.fromisoformat(spec['cutoff']).astimezone(UTC)
        assert call(state, 'post', '/predictions/run', {'period_id': period['id'], 'as_of': as_of.isoformat()}).status_code == 200

    before, audits = real_counts(state, period['id']), audit_count(state)
    response = call(state, 'get', f"/real-set?period_id={period['id']}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['period_code'] == period['code'] and body['is_locked'] is False and body['model_algorithm']
    assert body['students'] == body['total'] == len(body['items']) == STUDENTS and body['bimesters'] == ['B1', 'B2']
    assert 'full_name' not in response.text                                                 # solo códigos, nunca nombres
    for level in body['summary']:
        assert level['cuts'] == STUDENTS
        assert level['predicted_low'] + level['predicted_medium'] + level['predicted_high'] + level['predicted_missing'] == STUDENTS
        assert level['reference_low'] + level['reference_medium'] + level['reference_high'] == STUDENTS
        assert level['predicted_missing'] < STUDENTS
    with state.owner.connect() as conn:                                                      # niveles = predicción del modelo activo en el corte de la referencia
        expected = dict(conn.execute(text("""SELECT r.bimester||':'||s.anon_code, p.risk_level FROM risk_school.risk_references r
            JOIN risk_school.enrollments e ON e.id=r.enrollment_id JOIN risk_school.students s ON s.id=e.student_id
            LEFT JOIN risk_school.predictions p ON p.snapshot_id=r.snapshot_id AND p.model_id=:m WHERE r.period_id=:p"""),
            {'m': model_id, 'p': period['id']}).all())
        alerts = conn.scalar(text("""SELECT count(DISTINCT a.enrollment_id) FROM risk_school.alerts a
            JOIN risk_school.enrollments e ON e.id=a.enrollment_id WHERE e.period_id=:p"""), {'p': period['id']})
    got = {f"{cut['bimester']}:{item['anon_code']}": cut['predicted_risk'] for item in body['items'] for cut in item['cuts']}
    assert got == expected and body['alerts'] == alerts > 0
    first = body['items'][0]['cuts'][0]
    assert {'average_grade', 'attendance_pct', 'activities_pct', 'behavior_incidents', 'reference_points'} <= set(first)
    assert 'participation_level' not in response.text
    assert real_counts(state, period['id']) == before and audit_count(state) == audits         # consultar no escribe nada

    assert call(state, 'get', f'/real-set?period_id={state.period_id}').status_code == 404     # un periodo SYNTHETIC no es el conjunto real
    assert call(state, 'get', f'/real-set?period_id={uuid4()}').status_code == 404
    assert call(state, 'get', f"/real-set?period_id={period['id']}&section_id={uuid4()}").status_code == 404

    login_as(state, 'TUTOR')                                                                 # el tutor de la sección ve sus estudiantes
    assert call(state, 'get', f"/real-set?period_id={period['id']}").json()['total'] == STUDENTS
    login_as(state, 'DIRECTOR')
    assert call(state, 'get', f"/real-set?period_id={period['id']}").status_code == 200
    login_as(state, 'RESEARCHER')
    assert call(state, 'get', f"/real-set?period_id={period['id']}").status_code == 403

    login_as(state, 'ADMIN')                                                                 # cerrar el conjunto: el servidor rechaza escrituras
    with state.owner.connect() as conn:
        version = conn.scalar(text('SELECT version FROM risk_school.academic_periods WHERE id=:p'), {'p': period['id']})
        student, section = conn.execute(text('SELECT student_id,section_id FROM risk_school.enrollments WHERE period_id=:p LIMIT 1'),
                                        {'p': period['id']}).one()
    lock = {key: period[key] for key in ('code', 'school_year', 'start_date', 'end_date', 'data_origin')}
    assert write(state, f"/periods/{period['id']}", {**lock, 'creation_key': str(uuid4()), 'is_locked': True,
                                                     'expected_version': version}, 'patch').status_code == 200
    assert call(state, 'get', f"/real-set?period_id={period['id']}").json()['is_locked'] is True
    closed = real_counts(state, period['id'])
    attempts = [
        call(state, 'post', '/predictions/run', {'period_id': period['id'], 'as_of': datetime.now(UTC).isoformat()}),
        call(state, 'post', f"/students/{student}/evaluate?period_id={period['id']}"),
        write(state, '/students', dict(creation_key=str(uuid4()), anon_code='CERRADO-' + uuid4().hex[:6], full_name='Prueba Cierre',
                                       period_id=period['id'], section_id=str(section))),
        write(state, f"/students/{student}/measurements?period_id={period['id']}", dict(
            creation_key=str(uuid4()), window_start='2026-03-09', cutoff_at='2026-04-21T18:00:00-05:00',
            available_at='2026-04-21T17:00:00-05:00', purpose='PARTIAL', average_grade=10, attendance_pct=80, activities_pct=70,
            behavior_incidents=1)),
    ]
    assert all(response.status_code in (404, 409, 422) for response in attempts), [r.status_code for r in attempts]
    assert all(response.status_code == 409 for response in attempts[1:]), [r.status_code for r in attempts]
    assert real_counts(state, period['id']) == closed
