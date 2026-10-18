"""Bloque 2b: intervención oportuna POR INTERVENCIÓN (Tabla 6 de la tesis), junto a la versión por estudiante.

Los esperados se calculan a mano en la prueba, no con el SQL del servicio. DB aislada; datos SYNTHETIC.
"""
import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.ml.predict import PredictionResult
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo, new_student, measure, evaluate, HIGH  # noqa: F401
from test_b2_indicators import get, indicators, tutor_section

LIMA = ZoneInfo('America/Lima')
# código → (riesgo evaluado, [(estado, días tras la alerta, ligada a alerta)])
PLAN = {
    'a': ('HIGH', [('DONE', 14, True), ('DONE', 15, True)]),      # 2 intervenciones: día 14 sí, día 15 no
    'b': ('HIGH', [('DONE', 1, True)]),                           # 1 intervención oportuna
    'c': ('HIGH', []),                                            # 0 intervenciones
    'd': ('LOW', [('DONE', 2, False)]),                           # realizada sin alerta ligada
    'e': ('HIGH', [('PLANNED', None, True), ('CANCELLED', None, True)]),  # no cuentan
    'f': ('HIGH', [('DONE', 3, True)]),                           # inelegible: fuera de todo
}


@pytest.fixture
def cases(demo, monkeypatch):
    state = demo
    import app.ml.predict as predict
    state.section_id, state.other_sections = tutor_section(state)
    t0 = (datetime.now(UTC).astimezone(LIMA) - timedelta(days=40)).replace(hour=10, minute=0, second=0, microsecond=0)
    risks = {}
    monkeypatch.setattr(predict, 'predict_snapshot',
        lambda observation, bundle: PredictionResult('EVALUATED', risk_level=risks[observation.student_key]))
    state.people = {}
    for label, (risk, _) in PLAN.items():
        student = new_student(state)
        measure(state, student, HIGH)
        state.people[label] = student
        risks[student['id']] = risk
        assert evaluate(state, student).status_code == 200
    admin = state.context['accounts']['ADMIN']['id']
    with state.owner.begin() as conn:
        conn.execute(text('ALTER TABLE risk_school.alerts DISABLE TRIGGER USER'))
        conn.execute(text('ALTER TABLE risk_school.interventions DISABLE TRIGGER USER'))
        for label, (_, interventions) in PLAN.items():
            enrollment = conn.scalar(text('SELECT id FROM risk_school.enrollments WHERE student_id=:s AND period_id=:p'),
                                     {'s': state.people[label]['id'], 'p': state.period_id})
            alert = conn.scalar(text('SELECT id FROM risk_school.alerts WHERE enrollment_id=:e'), {'e': enrollment})
            if alert:
                conn.execute(text('UPDATE risk_school.alerts SET opened_at=:t,detected_at=:t WHERE id=:a'), {'t': t0, 'a': alert})
            for status, day, linked in interventions:
                performed = t0 + timedelta(days=day) if day is not None else None
                conn.execute(text('''INSERT INTO risk_school.interventions(id,enrollment_id,alert_id,data_origin,created_by,kind,
                    objective,status,scheduled_at,performed_at,version,creation_key,creation_payload_sha256)
                    VALUES(:id,:e,:a,'SYNTHETIC',:u,'TUTORING','Actividad simulada',:st,:sched,:perf,1,:k,repeat('a',64))'''),
                    {'id': uuid4(), 'e': enrollment, 'a': alert if linked else None, 'u': admin, 'st': status,
                     'sched': performed or t0 + timedelta(days=1), 'perf': performed, 'k': uuid4()})
        conn.execute(text('ALTER TABLE risk_school.alerts ENABLE TRIGGER USER'))
        conn.execute(text('ALTER TABLE risk_school.interventions ENABLE TRIGGER USER'))
        conn.execute(text('UPDATE risk_school.students SET eligible_for_processing=false WHERE id=:s'),
                     {'s': state.people['f']['id']})
    return state


def test_both_definitions_side_by_side(cases):
    state = cases
    total = indicators(state, section_id=str(state.section_id))['total']
    by_intervention = total['opportune_by_intervention']
    # Por intervención: realizadas ligadas a alerta y de estudiantes elegibles = a(2) + b(1) = 3;
    # oportunas = a día 14 y b día 1 = 2. La realizada sin alerta (d) se cuenta aparte; e (planificada/cancelada) y f no cuentan.
    assert (by_intervention['numerator'], by_intervention['denominator']) == (2, 3)
    assert by_intervention['percent'] == pytest.approx(100 * 2 / 3, abs=1e-3)
    assert by_intervention['without_alert'] == 1 and by_intervention['window_days'] == 14
    # Por estudiante (sin cambios): alertados = a, b, c, e → oportunos a (primera en día 14) y b = 2 de 4.
    by_student = total['opportune']
    assert (by_student['numerator'], by_student['denominator']) == (2, 4)
    # NIA sigue contando realizadas por estudiante elegible: a=2, b=1, d=1 → 4.
    assert total['nia']['total'] == 4
    # La tarjeta por sección coincide con el total cuando se filtra esa sección.
    body = indicators(state)
    mine = next(s for s in body['sections'] if s['section_id'] == str(state.section_id))
    assert mine['opportune_by_intervention']['numerator'] == 2 and mine['opportune_by_intervention']['denominator'] == 3
    others = [s for s in body['sections'] if s['section_id'] != str(state.section_id)]
    assert all(s['opportune_by_intervention']['percent'] is None and
               s['opportune_by_intervention']['reason'] == 'NO_INTERVENTIONS_LINKED_TO_ALERT' for s in others)


def test_without_interventions_is_null_not_zero(demo):
    ratio = indicators(demo)['total']['opportune_by_intervention']
    assert ratio['percent'] is None and ratio['numerator'] == 0 and ratio['denominator'] == 0
    assert ratio['reason'] == 'NO_INTERVENTIONS_LINKED_TO_ALERT' and ratio['without_alert'] == 0


def test_interventions_csv_rows_codes_only_and_permissions(cases):
    state = cases
    with state.owner.begin() as conn:
        conn.execute(text("UPDATE risk_school.students SET anon_code='=SUM(1)' WHERE id=:s"), {'s': state.people['b']['id']})
    params = dict(period_id=str(state.period_id), section_id=str(state.section_id))
    response = get(state, '/indicators/interventions.csv', **params)
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/csv')
    content = response.content.decode('utf-8-sig')
    assert 'Alumno de Prueba' not in content and 'full_name' not in content
    rows = list(csv.DictReader(io.StringIO(content)))
    assert list(rows[0]) == ['origen', 'alcance', 'periodo', 'as_of_utc', 'codigo_anonimo', 'grado', 'seccion',
                             'alerta_vinculada', 'fecha_alerta_utc', 'fecha_intervencion_utc', 'dias_desde_alerta', 'oportuna', 'metric_basis']  # 3B-3: columna de base de métricas
    assert len(rows) == 4  # una fila por intervención realizada elegible: a×2, b×1, d×1 (e y f no)
    by_code = {}
    for row in rows:
        by_code.setdefault(row['codigo_anonimo'], []).append(row)
    a_code, d_code = state.people['a']['anon_code'], state.people['d']['anon_code']
    assert sorted((r['dias_desde_alerta'], r['oportuna']) for r in by_code[a_code]) == [('14', 'SI'), ('15', 'NO')]
    assert [(r['alerta_vinculada'], r['dias_desde_alerta'], r['oportuna'], r['fecha_alerta_utc']) for r in by_code[d_code]] == [('NO', '', '', '')]
    assert "'=SUM(1)" in by_code and not any(code.startswith('=') for code in by_code)
    assert [(r['dias_desde_alerta'], r['oportuna']) for r in by_code["'=SUM(1)"]] == [('1', 'SI')]
    with state.owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE action='INDICATORS_INTERVENTIONS_EXPORT_REQUESTED'")) >= 1
    # Roles y sección.
    foreign = state.other_sections[0]
    for role, all_sections in (('TUTOR', False), ('DIRECTOR', True), ('RESEARCHER', True), ('ADMIN', True)):
        login_as(state, role)
        assert get(state, '/indicators/interventions.csv', period_id=str(state.period_id)).status_code == 200
        foreign_status = get(state, '/indicators/interventions.csv', period_id=str(state.period_id), section_id=str(foreign)).status_code
        assert foreign_status == (200 if all_sections else 404)
    state.client.cookies.clear()
    assert get(state, '/indicators/interventions.csv', period_id=str(state.period_id)).status_code == 401
    login_as(state, 'ADMIN')
    # TUTOR sin las intervenciones ajenas: el CSV sin filtro solo incluye su sección.
    login_as(state, 'TUTOR')
    mine = list(csv.DictReader(io.StringIO(get(state, '/indicators/interventions.csv', period_id=str(state.period_id))
                                           .content.decode('utf-8-sig'))))
    assert len(mine) == 4
    login_as(state, 'ADMIN')


def test_real_period_and_future_as_of_blocked(demo):
    state = demo
    period, _ = real_setup(state, 'REAL')
    response = get(state, '/indicators/interventions.csv', period_id=period['id'])
    assert response.status_code == 422 and response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    response = get(state, '/indicators/interventions.csv', period_id=str(state.period_id), as_of=future)
    assert response.status_code == 422 and response.json()['code'] == 'AS_OF_IN_FUTURE'
