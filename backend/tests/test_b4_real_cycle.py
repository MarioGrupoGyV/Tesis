"""Bloque 3B-2 (I): ciclo REAL completo con datos ficticios etiquetados REAL (ni un dato del colegio).

Protocolo → estudio institucional → importación de cortes → cierres (RIESGO_V1) → comparación → registro → activación →
evaluación retrospectiva en el corte → alertas con detected_at → indicadores. Con no mezcla en ambos sentidos.
"""
import random
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.ml.institutional import compare_institutional
from app.models.s1 import AppUser
from app.services import institutional_study, risk_reference_store, synthetic_study
from app.services.risk_reference import ClosingInputs
from app.services.risk_reference_store import ClosingRow
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo  # noqa: F401
from test_b3_protocol import body as protocol_body, call, ORIGIN

STUDENTS = 60
BIMESTERS = {
    'B1': dict(cutoff='2026-04-21T23:59:59-05:00', target='2026-05-08', closing_at='2026-05-11T12:00:00-05:00', window='2026-03-09'),
    'B2': dict(cutoff='2026-06-30T23:59:59-05:00', target='2026-07-17', closing_at='2026-07-20T12:00:00-05:00', window='2026-05-18'),
}
HEADER = 'student_code,grade,section,cutoff_at,target_date,available_at,window_start,average_grade,attendance_pct,activities_pct,' \
         'participation_level,behavior_incidents,age_years'


def clip(value, low, high):
    return max(low, min(high, value))


def fictitious_world(section_code, prefix):
    """CSV de cortes (sin participación: se deja vacía) y filas de cierre ficticias; el riesgo lo calcula el backend."""
    rng = random.Random(20261017)
    lines, closings = [HEADER], []
    for index in range(STUDENTS):
        code = f'{prefix}-{index:03d}'
        for bimester, spec in BIMESTERS.items():
            latent = clip(index / STUDENTS + rng.uniform(-0.08, 0.08), 0, 1)
            grade = round(clip(20 - 12 * latent + rng.uniform(-1.2, 1.2), 0, 20), 2)
            attendance = round(clip(100 - 45 * latent + rng.uniform(-5, 5), 0, 100), 2)
            activities = round(clip(100 - 60 * latent + rng.uniform(-6, 6), 0, 100), 2)
            incidents = int(clip(round(6 * latent + rng.uniform(-1, 1)), 0, 9))
            lines.append(','.join([code, '1', section_code, spec['cutoff'], spec['target'], spec['cutoff'], spec['window'],
                                   f'{grade:.2f}', f'{attendance:.2f}', f'{activities:.2f}', '', str(incidents), '']))
            closings.append(dict(student_code=code, bimester=bimester, closing_date=date.fromisoformat(spec['target']),
                closing_available_at=datetime.fromisoformat(spec['closing_at']),
                inputs=ClosingInputs(average_grade=Decimal(f'{grade:.2f}'), days_scheduled=45,
                                     days_attended=round(45 * attendance / 100), activities_scheduled=24,
                                     activities_delivered=round(24 * activities / 100),
                                     participation_level=int(clip(5 - round(4 * latent), 1, 5)), behavior_incidents=incidents)))
    return ('\n'.join(lines) + '\n').encode(), closings


def admin(state, db):
    return db.get(AppUser, state.context['accounts']['ADMIN']['id'])


def blocked_everywhere(state, period_id, student_id):
    now = datetime.now(UTC).isoformat()
    attempts = [call(state, 'get', f'/alerts?period_id={period_id}'), call(state, 'post', '/alerts/sync', {'period_id': period_id}),
                call(state, 'get', f'/reports/summary?period_id={period_id}'), call(state, 'get', f'/reports/export.csv?period_id={period_id}'),
                call(state, 'get', f'/indicators?period_id={period_id}'), call(state, 'get', f'/indicators/students?period_id={period_id}'),
                call(state, 'get', f'/indicators/export.csv?period_id={period_id}'),
                call(state, 'post', '/predictions/run', {'period_id': period_id, 'as_of': now}),
                call(state, 'post', f'/students/{student_id}/evaluate?period_id={period_id}'),
                state.client.post(API + '/imports/preview', data={'period_id': period_id},
                                  files={'file': ('x.csv', b'student_code\n', 'text/csv')}, headers={'X-CSRF-Token': state.csrf, **ORIGIN})]
    for response in attempts:
        assert response.status_code == 422 and response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY', response.text[:150]


def test_full_real_cycle_with_fictitious_data(demo):
    state = demo
    period, section = real_setup(state, 'REAL')
    with state.owner.connect() as conn:
        synthetic_model = conn.scalar(text("SELECT id FROM risk_school.model_versions WHERE data_origin='SYNTHETIC' AND is_active"))
        names_before = conn.scalar(text('SELECT count(*) FROM risk_school.students'))
    # Alumno con nombre en M1: los nombres nunca deben aparecer en indicadores ni en sus CSV.
    named = write(state, '/students', dict(creation_key=str(uuid4()), anon_code='R-NAMED-' + uuid4().hex[:6], full_name='Zzxqwv Prueba Apellidoz',
                                           period_id=period['id'], section_id=section['id'])).json()
    protocol = call(state, 'post', '/processing-protocols', protocol_body(period['id'])).json()
    blocked_everywhere(state, period['id'], named['id'])                        # sin protocolo confirmado: todo REAL bloqueado

    prefix = 'R' + uuid4().hex[:6]
    content, closings = fictitious_world(section['code'], prefix)
    with state.app.state.database.session_factory() as db:
        with pytest.raises(Exception) as error:                                  # registrar el estudio también exige protocolo
            institutional_study.register_study(db, admin(state, db), state.settings, UUID(protocol['id']), content, uuid4())
        assert getattr(error.value, 'code', '') == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm").json()['authorization_confirmed_by_admin'] is True
    with state.owner.connect() as conn:    # confirmar cubre las matrículas ya registradas del periodo, sin fabricar consentimientos
        assert tuple(conn.execute(text('SELECT eligible_for_processing,consent_documented,assent_documented FROM risk_school.students WHERE id=:s'),
                                  {'s': named['id']}).one()) == (True, False, False)

    # Estudio institucional + importación por la API (CSV canónico exacto registrado).
    with state.app.state.database.session_factory() as db:
        study, reused = institutional_study.register_study(db, admin(state, db), state.settings, UUID(protocol['id']), content, uuid4())
        assert reused is False and study.kind == 'INSTITUTIONAL_STUDY' and study.manifest['rows'] == 2 * STUDENTS
        assert institutional_study.register_study(db, admin(state, db), state.settings, UUID(protocol['id']), content, uuid4())[1] is True
        study_id = study.id
    other = call(state, 'post', f"/students/{named['id']}/evaluate?period_id={period['id']}")
    assert other.status_code == 409 and other.json()['code'] == 'MODEL_NOT_AVAILABLE'   # sin modelo REAL aún
    wrong = state.client.post(API + '/imports/preview', data={'period_id': period['id']},
        files={'file': ('x.csv', content.replace((prefix + '-000').encode(), (prefix + '-999').encode()), 'text/csv')}, headers={'X-CSRF-Token': state.csrf, **ORIGIN})
    assert wrong.status_code == 422 and wrong.json()['code'] == 'UNREGISTERED_INSTITUTIONAL_FILE'
    preview = state.client.post(API + '/imports/preview', data={'period_id': period['id']},
        files={'file': ('cortes.csv', content, 'text/csv')}, headers={'X-CSRF-Token': state.csrf, **ORIGIN})
    assert preview.status_code == 201, preview.text
    batch = preview.json()
    assert batch['status'] == 'READY' and batch['data_origin'] == 'REAL' and batch['total_rows'] == 2 * STUDENTS
    committed = state.client.post(API + f"/imports/{batch['id']}/commit", json={'expected_preview_version': batch['preview_version']},
                                  headers={'X-CSRF-Token': state.csrf, **ORIGIN})
    assert committed.status_code == 200, committed.text
    with state.owner.connect() as conn:
        flags = conn.execute(text("""SELECT count(*),count(*) FILTER (WHERE eligible_for_processing),
            count(*) FILTER (WHERE consent_documented OR assent_documented) FROM risk_school.students WHERE data_origin='REAL' AND anon_code LIKE :p"""), {'p': prefix + '-%'}).one()
        assert tuple(flags) == (STUDENTS, STUDENTS, 0)                          # elegibles por protocolo; sin consentimientos fabricados
        assert conn.scalar(text("SELECT bindings IS NOT NULL AND jsonb_array_length(bindings)=:n FROM risk_school.synthetic_studies WHERE id=:s"),
                           {'n': 2 * STUDENTS, 's': study_id})

    # Cierres → riesgo de referencia calculado por el backend (RIESGO_V1); comparación sin cierres: datos insuficientes.
    with state.app.state.database.session_factory() as db:
        with pytest.raises(Exception) as error:
            synthetic_study.compare_registered(db, admin(state, db), state.settings, study_id, uuid4())
        assert getattr(error.value, 'code', '') == 'INSUFFICIENT_DATA_FOR_STUDY'
        loaded = risk_reference_store.load_closings(db, admin(state, db), UUID(period['id']),
            [ClosingRow(line=i + 2, **item) for i, item in enumerate(closings)], uuid4())
        assert loaded['created'] == 2 * STUDENTS

    # Comparación (CV agrupada repetida), registro y activación; el modelo SYNTHETIC activo no se toca.
    with state.app.state.database.session_factory() as db:
        user = admin(state, db)
        report = synthetic_study.compare_registered(db, user, state.settings, study_id, uuid4())
        assert report['reused'] is False and report['approval_kind'] == 'LOCAL_EXPLORATORY' and report['repetitions'] == 20
        assert set(report['algorithms']) == {'DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST'}
        assert any('n = 60 estudiantes' in note for note in report['warnings'])
        assert set(report['support_by_class']) == {'LOW', 'MEDIUM', 'HIGH'}
        assert synthetic_study.compare_registered(db, user, state.settings, study_id, uuid4())['reused'] is True
        stored = db.scalar(text('SELECT comparison FROM risk_school.synthetic_studies WHERE id=:s'), {'s': study_id})
        # Reproducibilidad: misma semilla y mismo dataset → mismo informe.
        study = synthetic_study.get_study(db, study_id)
        protocol_row, _, _ = institutional_study.validate_institutional(db, state.settings, study)
        dataset, _ = institutional_study.build_dataset(db, study, protocol_row)
        again = compare_institutional(dataset, seed=int(study.seed), study_id=study.id)
        assert again.report['report_sha256'] == stored['report']['report_sha256']
        model, was_reused = synthetic_study.register_model(db, user, state.settings, study_id, None, uuid4())
        assert was_reused is False and model.data_origin == 'REAL' and model.manifest['approval_kind'] == 'LOCAL_EXPLORATORY'
        assert model.manifest['scope'] == 'INSTITUTIONAL_STUDY' and model.manifest['feature_schema']['base_features'] == institutional_study.FEATURES
        activated, was_active = synthetic_study.activate_model(db, user, state.settings, model.id, uuid4())
        assert activated.is_active is True and was_active is False
        real_model = model.id
    with state.owner.connect() as conn:
        active = dict(conn.execute(text('SELECT data_origin,id FROM risk_school.model_versions WHERE is_active')).all())
        assert active['REAL'] == real_model and active['SYNTHETIC'] == synthetic_model       # uno activo por origen, sin cruzarse

    # Evaluación retrospectiva en cada corte: predicted_at real, as_of_at y detected_at simulados.
    for bimester, spec in BIMESTERS.items():
        as_of = datetime.fromisoformat(spec['cutoff']).replace(hour=23, minute=59, second=59).astimezone(UTC)
        response = call(state, 'post', '/predictions/run', {'period_id': period['id'], 'as_of': as_of.isoformat()})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['model_id'] == str(real_model) and result['created'] + result['reused'] >= STUDENTS - len(result['abstentions'])
        assert result['followup']['created'] + result['followup']['updated'] > 0
    with state.owner.connect() as conn:
        rows = conn.execute(text("""SELECT count(*), count(*) FILTER (WHERE p.as_of_at < p.predicted_at - interval '1 day'),
            count(*) FILTER (WHERE p.model_id<>:m) FROM risk_school.predictions p JOIN risk_school.enrollments e ON e.id=p.enrollment_id
            WHERE e.period_id=:p"""), {'m': real_model, 'p': period['id']}).one()
        assert rows[0] >= 2 * STUDENTS - 10 and rows[1] == rows[0] and rows[2] == 0
        alerts = conn.execute(text("""SELECT count(*), count(*) FILTER (WHERE a.detected_at < a.opened_at - interval '1 day'),
            count(*) FILTER (WHERE a.data_origin<>'REAL') FROM risk_school.alerts a JOIN risk_school.enrollments e ON e.id=a.enrollment_id
            WHERE e.period_id=:p"""), {'p': period['id']}).one()
        assert alerts[0] > 0 and alerts[1] == alerts[0] and alerts[2] == 0
        assert conn.scalar(text("SELECT count(*) FROM risk_school.alerts a JOIN risk_school.enrollments e ON e.id=a.enrollment_id WHERE e.period_id=:p AND a.status IN ('OPEN','IN_REVIEW')"),
                           {'p': period['id']}) <= STUDENTS                       # una alerta activa por matrícula
        # El período sintético no recibió nada del modelo REAL y viceversa (la BD ya lo impide; aquí se comprueba el resultado).
        assert conn.scalar(text("SELECT count(*) FROM risk_school.predictions p WHERE p.data_origin='SYNTHETIC' AND p.model_id=:m"), {'m': real_model}) == 0

    # Indicadores REAL por bimestre: etiquetas, retrospectiva, NIA/oportuna nulos con motivo, métricas y CSV sin nombres.
    for bimester in BIMESTERS:
        response = call(state, 'get', f"/indicators?period_id={period['id']}&bimester={bimester}")
        assert response.status_code == 200, response.text
        data = response.json()
        total = data['total']
        assert data['data_origin'] == 'REAL' and data['is_simulation'] is False and data['bimester'] == bimester
        assert data['notice'].startswith('Datos reales locales — análisis exploratorio, no demuestra eficacia escolar')
        assert data['opportune_window_days'] == 5 and data['retrospective_alerts'] > 0
        assert total['nia']['reason'] == 'NO_REAL_INTERVENTIONS' and total['nia']['total'] is None
        assert total['opportune']['percent'] is None and total['opportune']['reason'] == 'NO_REAL_INTERVENTIONS'
        assert total['pder']['denominator'] > 0 and total['pder']['percent'] is not None   # detectadas antes del cierre del bimestre
        assert total['model_metrics']['n'] > 0 and total['eligible_students'] == STUDENTS + 1
    assert call(state, 'get', f"/indicators?period_id={period['id']}&bimester=NOPE").status_code == 404
    assert call(state, 'get', f"/indicators?period_id={state.period_id}&bimester=B1").status_code == 422       # bimestre solo en REAL
    contexts = call(state, 'get', '/indicators/contexts').json()
    assert {c['data_origin'] for c in contexts} == {'SYNTHETIC', 'REAL'}
    real_context = next(c for c in contexts if c['data_origin'] == 'REAL')
    assert real_context['bimesters'] == ['B1', 'B2']
    csv_texts = [call(state, 'get', f"/indicators/export.csv?period_id={period['id']}&bimester=B1").text,
                 call(state, 'get', f"/indicators/interventions.csv?period_id={period['id']}").text]
    for text_ in csv_texts:
        assert 'Zzxqwv' not in text_ and 'Apellidoz' not in text_ and 'Alumno' not in text_      # solo códigos, nunca nombres
    assert csv_texts[0].splitlines()[0].endswith('fecha_deteccion_utc,simulacion_retrospectiva')
    assert csv_texts[0].splitlines()[1].startswith('REAL,INSTITUTIONAL_STUDY,')
    # Lista y detalle de alertas / resumen funcionan para REAL con los permisos habituales.
    assert call(state, 'get', f"/alerts?period_id={period['id']}").status_code == 200
    summary = call(state, 'get', f"/reports/summary?period_id={period['id']}")
    assert summary.status_code == 200, summary.text

    # Evaluación individual del último corte reutiliza la predicción ya creada.
    with state.owner.connect() as conn:
        student_id = conn.scalar(text("SELECT s.id FROM risk_school.students s WHERE s.anon_code=:c"), {'c': prefix + '-010'})
    evaluation = call(state, 'post', f"/students/{student_id}/evaluate?period_id={period['id']}")
    assert evaluation.status_code == 200 and evaluation.json()['status'] == 'EVALUATED' and evaluation.json()['prediction_reused'] is True

    # El periodo SYNTHETIC conserva su modelo y su flujo; la tabla de modelos lista ambos orígenes.
    models = call(state, 'get', '/models').json()
    assert {m['data_origin'] for m in models['items'] if m['is_active']} == {'SYNTHETIC', 'REAL'}

    # No mezcla a nivel de API: el periodo SYNTHETIC se evalúa con su propio modelo aunque exista un modelo REAL activo.
    synthetic_run = call(state, 'post', '/predictions/run', {'period_id': str(state.period_id), 'as_of': datetime.now(UTC).isoformat()})
    assert synthetic_run.status_code == 200, synthetic_run.text
    assert synthetic_run.json()['model_id'] == str(synthetic_model) and synthetic_run.json()['model_id'] != str(real_model)

    # Revocar el protocolo vuelve a bloquear todo REAL de inmediato, sin tocar lo ya guardado.
    call(state, 'post', f"/processing-protocols/{protocol['id']}/revoke")
    blocked_everywhere(state, period['id'], student_id)
    with state.owner.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM risk_school.students')) >= names_before + STUDENTS
    assert call(state, 'get', f"/students?period_id={state.period_id}").status_code == 200   # SYNTHETIC sigue operativo
