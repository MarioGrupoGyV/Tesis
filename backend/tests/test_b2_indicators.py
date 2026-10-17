"""Bloque 2: indicadores de la tesis. Cada resultado esperado se calcula aquí con una vía
independiente (valores construidos a mano y Python puro), no con el SQL del servicio.

DB y artefactos aislados; los datos son simulación SYNTHETIC, no resultados del colegio.
"""
import csv
import io
from datetime import UTC, datetime, timedelta
from statistics import mean, median
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.ml.predict import PredictionResult
from app.models.s1 import AppUser
from app.services import ml
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo, new_student, measure, evaluate, post, HIGH  # noqa: F401

LIMA = ZoneInfo('America/Lima')


def get(state, path, **params):
    return state.client.get(API + path, params=params)


def indicators(state, **params):
    response = get(state, '/indicators', period_id=str(state.period_id), **params)
    assert response.status_code == 200, response.text
    return response.json()


def tutor_section(state):
    with state.owner.connect() as conn:
        mine = conn.scalar(text('''SELECT g.id FROM risk_school.grade_sections g WHERE g.tutor_id=:t AND EXISTS(
            SELECT 1 FROM risk_school.enrollments e WHERE e.section_id=g.id AND e.period_id=:p)'''),
                           {'t': state.context['accounts']['TUTOR']['id'], 'p': state.period_id})
        other = conn.scalars(text('SELECT DISTINCT section_id FROM risk_school.enrollments WHERE period_id=:p AND section_id<>:m'),
                             {'p': state.period_id, 'm': mine}).all()
    return mine, other


def eligible_in_section(state, section):
    with state.owner.connect() as conn:
        return conn.scalar(text('''SELECT count(*) FROM risk_school.enrollments e JOIN risk_school.students s ON s.id=e.student_id
            WHERE e.period_id=:p AND e.section_id=:g AND s.is_active AND s.eligible_for_processing'''),
            {'p': state.period_id, 'g': section})


@pytest.fixture
def scenario(demo, monkeypatch):
    """10 alumnos manuales con alertas/intervenciones en fechas conocidas (T0 = hace 40 días, 10:00 Lima)."""
    state = demo
    import app.ml.predict as predict
    section, others = tutor_section(state)
    state.section_id, state.other_sections = section, others
    state.base_eligible = eligible_in_section(state, section)
    now_lima = datetime.now(UTC).astimezone(LIMA)
    t0 = (now_lima - timedelta(days=40)).replace(hour=10, minute=0, second=0, microsecond=0)
    state.t0 = t0
    plan = {  # código → (riesgo evaluado o None, [(desplazamiento de la actividad realizada, días)], solo planificada)
        's1': ('HIGH', [3], False), 's2': ('HIGH', [14], False), 's3': ('HIGH', [15], False), 's4': ('HIGH', [], False),
        's5': ('HIGH', [], True), 's6': ('HIGH', [2, 20], False), 's7': ('LOW', [], False), 's8': (None, [], False),
        's9': ('MEDIUM', [0], False), 's10': ('HIGH', [4], False)}
    risks = {}
    monkeypatch.setattr(predict, 'predict_snapshot',
        lambda observation, bundle: PredictionResult('EVALUATED', risk_level=risks[observation.student_key]))
    state.people = {}
    for label, (risk, _, _) in plan.items():
        student = new_student(state)
        measure(state, student, HIGH)
        state.people[label] = student
        if risk:
            risks[student['id']] = risk
            assert evaluate(state, student).status_code == 200
    admin_id = state.context['accounts']['ADMIN']['id']
    with state.owner.begin() as conn:
        conn.execute(text('ALTER TABLE risk_school.alerts DISABLE TRIGGER USER'))
        conn.execute(text('ALTER TABLE risk_school.interventions DISABLE TRIGGER USER'))
        for label, (risk, done, planned_only) in plan.items():
            student = state.people[label]
            enrollment = conn.scalar(text('SELECT id FROM risk_school.enrollments WHERE student_id=:s AND period_id=:p'),
                                     {'s': student['id'], 'p': state.period_id})
            alert = conn.scalar(text('SELECT id FROM risk_school.alerts WHERE enrollment_id=:e'), {'e': enrollment})
            if alert:
                conn.execute(text('UPDATE risk_school.alerts SET opened_at=:t WHERE id=:a'), {'t': t0, 'a': alert})
            rows = [('DONE', t0 + timedelta(days=d)) for d in done] + ([('PLANNED', None)] if planned_only else [])
            for status, performed in rows:
                conn.execute(text('''INSERT INTO risk_school.interventions(id,enrollment_id,alert_id,data_origin,created_by,kind,
                    objective,status,scheduled_at,performed_at,version,creation_key,creation_payload_sha256)
                    VALUES(:id,:e,:a,'SYNTHETIC',:u,'TUTORING','Actividad simulada',:st,:sched,:perf,1,:k,repeat('a',64))'''),
                    {'id': uuid4(), 'e': enrollment, 'a': alert, 'u': admin_id, 'st': status,
                     'sched': performed or t0 + timedelta(days=1), 'perf': performed, 'k': uuid4()})
        conn.execute(text('ALTER TABLE risk_school.alerts ENABLE TRIGGER USER'))
        conn.execute(text('ALTER TABLE risk_school.interventions ENABLE TRIGGER USER'))
        conn.execute(text('UPDATE risk_school.students SET eligible_for_processing=false WHERE id=:s'),
                     {'s': state.people['s10']['id']})
    return state


def test_manual_scenario_nia_opportune_cra_and_exclusions(scenario):
    state = scenario
    body = indicators(state, section_id=str(state.section_id))
    total = body['total']
    eligible = state.base_eligible + 9  # s1..s9; s10 es inelegible y queda fuera de todo
    assert body['is_simulation'] is True and body['opportune_window_days'] == 14
    assert total['eligible_students'] == eligible
    # CRA: evaluados s1..s7 y s9 = 8; s8 sin evaluación; s7 es LOW (sin alerta, cubierto) → 8 de `eligible`.
    assert (total['cra']['numerator'], total['cra']['denominator']) == (8, eligible)
    assert total['cra']['percent'] == pytest.approx(100 * 8 / eligible, abs=1e-3)
    # NIA: solo realizadas. s1=1, s2=1, s3=1, s4=0, s5=0 (planificada), s6=2, s9=1 → 6; s10 no cuenta.
    assert total['nia']['total'] == 6 and total['nia']['students'] == eligible
    assert total['nia']['mean'] == pytest.approx(6 / eligible, abs=1e-3)
    assert total['nia']['alerted_students'] == 7  # s1..s6 y s9
    assert total['nia']['mean_alerted'] == pytest.approx(mean([1, 1, 1, 0, 0, 2, 1]), abs=1e-3)
    assert total['nia']['median_alerted'] == median([1, 1, 1, 0, 0, 2, 1])
    # Oportuna (≤14 días calendario Lima): s1 (3), s2 (14, límite exacto), s6 (2), s9 (0) = 4 de 7 con alerta.
    # s3 (día 15), s4 (sin intervención) y s5 (solo planificada) no cuentan.
    assert (total['opportune']['numerator'], total['opportune']['denominator']) == (4, 7)
    assert total['opportune']['percent'] == pytest.approx(100 * 4 / 7, abs=1e-3)
    assert total['opportune']['students_with_first_intervention'] == 5
    assert total['opportune']['median_days_to_first'] == median([3, 14, 15, 2, 0])
    # Sin riesgo de referencia para estudiantes manuales: excluidos y contados, nunca inventados.
    assert total['exclusions']['ineligible'] == 1 and total['exclusions']['no_reference'] >= 9
    assert body['prv']['reason'] == 'PERIOD_LEVEL_ONLY'  # filtrado por sección
    # Detalle por estudiante.
    page = get(state, '/indicators/students', period_id=str(state.period_id), section_id=str(state.section_id),
               page_size=100).json()
    by_id = {state.people[k]['anon_code']: k for k in state.people}
    items = {by_id[i['anon_code']]: i for i in page['items'] if i['anon_code'] in by_id}
    assert items['s2']['opportune'] is True and items['s2']['days_to_first_intervention'] == 14 and items['s2']['nia'] == 1
    assert items['s3']['opportune'] is False and items['s3']['days_to_first_intervention'] == 15
    assert items['s4']['opportune'] is False and items['s4']['days_to_first_intervention'] is None and items['s4']['nia'] == 0
    assert items['s5']['opportune'] is False and items['s5']['nia'] == 0
    assert items['s6']['nia'] == 2 and items['s6']['days_to_first_intervention'] == 2
    assert items['s7']['opportune'] is None and items['s7']['alert_opened_at'] is None and items['s7']['predicted_risk'] == 'LOW'
    assert items['s8']['predicted_risk'] is None
    assert items['s10']['eligible'] is False and items['s10']['exclusion_reason'] == 'NOT_ELIGIBLE'
    assert all(i['reference_risk'] is None for i in items.values())


def test_exports_and_permissions(scenario):
    state = scenario
    # CSV: sin nombres, con códigos y neutralización de fórmulas.
    with state.owner.begin() as conn:
        conn.execute(text("UPDATE risk_school.students SET anon_code='=HYPERLINK(\"http://x\")' WHERE id=:s"),
                     {'s': state.people['s1']['id']})
    response = get(state, '/indicators/export.csv', period_id=str(state.period_id), section_id=str(state.section_id))
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/csv')
    assert response.content.startswith(b'\xef\xbb\xbf')
    content = response.content.decode('utf-8-sig')
    assert 'Alumno de Prueba' not in content and 'full_name' not in content
    rows = list(csv.reader(io.StringIO(content)))
    assert rows[0][:8] == ['origen', 'alcance', 'periodo', 'as_of_utc', 'codigo_anonimo', 'grado', 'seccion', 'elegible']
    assert any(row[4].startswith("'=") for row in rows[1:]) and not any(row[4].startswith('=') for row in rows[1:])
    # Roles: TUTOR solo su sección; DIRECTOR/RESEARCHER todo; sección ajena = 404.
    foreign = state.other_sections[0]
    for role, sees_all in (('TUTOR', False), ('DIRECTOR', True), ('RESEARCHER', True), ('ADMIN', True)):
        login_as(state, role)
        body = indicators(state)
        ids = {s['section_id'] for s in body['sections']}
        assert (str(foreign) in ids) == sees_all and str(state.section_id) in ids
        if not sees_all:
            assert ids == {str(state.section_id)} and body['prv']['reason'] == 'PERIOD_LEVEL_ONLY'
            assert get(state, '/indicators', period_id=str(state.period_id), section_id=str(foreign)).status_code == 404
            assert get(state, '/indicators/students', period_id=str(state.period_id), section_id=str(foreign)).status_code == 404
        else:
            assert body['prv']['received'] is not None
        assert get(state, '/indicators/export.csv', period_id=str(state.period_id)).status_code == 200
    # Sin sesión.
    state.client.cookies.clear()
    assert get(state, '/indicators', period_id=str(state.period_id)).status_code == 401
    login_as(state, 'ADMIN')


def test_real_period_blocked_and_future_as_of_rejected(demo):
    state = demo
    period, _ = real_setup(state, 'REAL')
    for path in ('/indicators', '/indicators/students', '/indicators/export.csv'):
        response = get(state, path, period_id=period['id'])
        assert response.status_code == 422 and response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    response = get(state, '/indicators', period_id=str(state.period_id), as_of=future)
    assert response.status_code == 422 and response.json()['code'] == 'AS_OF_IN_FUTURE'


def test_prv_matches_batch_and_row_counts(demo):
    state = demo
    login_as(state, 'ADMIN')
    expected_received = len(state.content.decode('utf-8').strip().splitlines()) - 1  # filas de datos del CSV
    body = indicators(state)
    prv = body['prv']
    with state.owner.connect() as conn:
        snapshots = conn.execute(text('''SELECT s.eligible_for_processing FROM risk_school.academic_snapshots sn
            JOIN risk_school.enrollments e ON e.id=sn.enrollment_id JOIN risk_school.students s ON s.id=e.student_id
            WHERE sn.period_id=:p AND sn.entry_channel='CSV' ''')
            , {'p': state.period_id}).all()
    processed = sum(1 for (flag,) in snapshots if flag)
    assert prv['received'] == expected_received and prv['rejected'] == 0 and prv['valid_not_committed'] == 0
    assert prv['valid_processed'] == processed and prv['ineligible_omitted'] == len(snapshots) - processed
    assert prv['denominator'] == expected_received and prv['numerator'] == processed
    assert prv['percent'] == pytest.approx(100 * processed / expected_received, abs=1e-3)
    assert prv['manual_measurements'] == 0


def test_reference_metrics_and_pder_against_regenerated_labels(demo):
    state = demo
    from app.ml.synthetic import generate, load_config
    generated = generate(load_config(None), state.seed)
    reference = {(o['student_code'], datetime.fromisoformat(o['cutoff_at'])): o['risk'] for o in generated.labels_json['outcomes']}
    with state.owner.connect() as conn:
        rows = conn.execute(text('''SELECT s.anon_code,sn.id,sn.cutoff_at,sn.revision,s.eligible_for_processing,s.is_active
            FROM risk_school.academic_snapshots sn JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
            JOIN risk_school.students s ON s.id=e.student_id WHERE sn.period_id=:p'''), {'p': state.period_id}).all()
    latest = {}
    for code, snapshot, cutoff, revision, eligible, active in rows:  # último corte por estudiante, en Python
        if code not in latest or (cutoff, revision) > (latest[code][1], latest[code][2]):
            latest[code] = (snapshot, cutoff, revision, bool(eligible and active))
    eligible_codes = sorted(code for code, value in latest.items() if value[3])
    subset = eligible_codes[:12]
    cycle = ('LOW', 'MEDIUM', 'HIGH')
    predicted = {code: cycle[index % 3] for index, code in enumerate(subset)}
    admin = state.context['accounts']['ADMIN']['id']
    with state.app.state.database.session_factory() as db:
        for code in subset:
            ml.persist_evaluated(db, snapshot_id=latest[code][0], model_id=state.model_id,
                result=PredictionResult('EVALUATED', risk_level=predicted[code]), actor_id=admin, request_id=uuid4())
        db.commit()
    assert state.client.post(API + '/alerts/sync', json={'period_id': str(state.period_id)},
                             headers={'X-CSRF-Token': state.csrf}).status_code == 200
    close_future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    body = get(state, '/indicators', period_id=str(state.period_id), close_at=close_future).json()
    total = body['total']
    ref = {code: reference[(code, latest[code][1])] for code in eligible_codes}
    assert total['eligible_students'] == len(eligible_codes)
    # CRA: los 12 evaluados están cubiertos (LOW por evaluación; MEDIUM/HIGH por alerta creada).
    assert (total['cra']['numerator'], total['cra']['denominator']) == (len(subset), len(eligible_codes))
    risky = [code for code in eligible_codes if ref[code] in ('MEDIUM', 'HIGH')]
    detected = [code for code in risky if predicted.get(code) in ('MEDIUM', 'HIGH')]
    assert (total['pder']['numerator'], total['pder']['denominator']) == (len(detected), len(risky))
    # Con un cierre anterior a las alertas, ninguna es oportuna para PDER (numerador 0, mismo denominador).
    past = get(state, '/indicators', period_id=str(state.period_id), close_at='2000-01-01T00:00:00Z').json()['total']['pder']
    assert (past['numerator'], past['denominator']) == (0, len(risky))
    # Métricas: matriz (referencia en filas, predicho en columnas) calculada a mano.
    index = {name: i for i, name in enumerate(cycle)}
    matrix = [[0] * 3 for _ in range(3)]
    for code in subset:
        matrix[index[ref[code]]][index[predicted[code]]] += 1
    metrics = total['model_metrics']
    assert metrics['n'] == len(subset) and metrics['confusion_matrix'] == matrix
    assert metrics['accuracy'] == pytest.approx(sum(matrix[i][i] for i in range(3)) / len(subset))
    for name, i in index.items():
        support, selected, hits = sum(matrix[i]), sum(row[i] for row in matrix), matrix[i][i]
        per = metrics['per_class'][name]
        assert per['support'] == support
        assert per['precision'] == (pytest.approx(hits / selected) if selected else None)
        assert per['recall'] == (pytest.approx(hits / support) if support else None)
    # Estudiantes sin referencia no entran; los CSV exponen el riesgo de referencia por código.
    page = get(state, '/indicators/students', period_id=str(state.period_id), page_size=100).json()
    shown = {i['anon_code']: i for i in page['items']}
    assert all(shown[code]['reference_risk'] == ref[code] for code in eligible_codes[:20] if code in shown)


def test_reference_not_available_is_null_with_reason(study_env):
    state = study_env
    prepare(state)  # estudio preparado, sin importar: no hay cortes vinculados ni referencia
    login_as(state, 'ADMIN')
    body = indicators(state)
    assert body['total']['pder']['percent'] is None and body['total']['pder']['reason'] == 'REFERENCE_NOT_AVAILABLE'
    assert body['total']['model_metrics'] is None and body['total']['model_metrics_reason'] == 'REFERENCE_NOT_AVAILABLE'
    assert body['prv']['received'] == 0 and body['prv']['percent'] is None
