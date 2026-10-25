"""Bloque 9 (ADR 014): copia de demostración del SVM REAL activo en DEMO-VIVO y retiro de la participación de las respuestas.

Datos ficticios. Una sola instalación de prueba con un ciclo REAL completo (modelo REAL activo) y el periodo sintético renombrado DEMO-VIVO.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pandas as pd
import pytest
from sqlalchemy import text

from app.core.errors import AppError
from app.ml.artifacts import ArtifactStore
from app.ml.predict import class_mapping, predict_snapshot
from app.models.ml import ModelVersion
from app.models.s1 import AcademicPeriod, AppUser
from app.models.synthetic import SyntheticStudyRecord
from app.services import demo_copy, institutional_study, risk_reference_store, synthetic_study
from app.services.ml import load_active_model
from app.services.risk_reference_store import ClosingRow
from test_s3_1_integration import study_env, prepare, import_study, login_as, API  # noqa: F401
from test_m1_manual import setup as real_setup, write, database_urls, owner_engine  # noqa: F401
from conftest import database_urls as _database_urls  # noqa: F401  (BD propia)
from test_b1_manual_evaluation import demo  # noqa: F401
from test_b3_protocol import body as protocol_body, call, ORIGIN
from test_b4_real_cycle import STUDENTS, fictitious_world

FEATURES = ('average_grade', 'attendance_pct', 'activities_pct', 'behavior_incidents')
# Tres casos (promedio, asistencia, tareas, incidencias): extremos para Alto y Bajo y uno intermedio.
CASES = {'HIGH': (6.0, 45.0, 30.0, 7), 'MEDIUM': (12.5, 82.0, 66.0, 3), 'LOW': (18.5, 98.0, 97.0, 0)}


def admin(state, db):
    return db.get(AppUser, state.context['accounts']['ADMIN']['id'])


def real_cycle(state):
    """Periodo REAL con protocolo confirmado, estudio, importación, cierres y SVM/otro modelo REAL activo (como la corrida real)."""
    period, section = real_setup(state, 'REAL')
    protocol = call(state, 'post', '/processing-protocols', protocol_body(period['id'])).json()
    assert call(state, 'post', f"/processing-protocols/{protocol['id']}/confirm").status_code == 200
    content, closings = fictitious_world(section['code'], 'R' + uuid4().hex[:6])
    with state.app.state.database.session_factory() as db:
        study, _ = institutional_study.register_study(db, admin(state, db), state.settings, UUID(protocol['id']), content, uuid4())
        study_id = study.id
    preview = state.client.post(API + '/imports/preview', data={'period_id': period['id']},
                                files={'file': ('cortes.csv', content, 'text/csv')}, headers={'X-CSRF-Token': state.csrf, **ORIGIN})
    batch = preview.json()
    assert state.client.post(API + f"/imports/{batch['id']}/commit", json={'expected_preview_version': batch['preview_version']},
                             headers={'X-CSRF-Token': state.csrf, **ORIGIN}).status_code == 200
    with state.app.state.database.session_factory() as db:
        risk_reference_store.load_closings(db, admin(state, db), UUID(period['id']),
                                           [ClosingRow(line=i + 2, **item) for i, item in enumerate(closings)], uuid4())
        user = admin(state, db)
        synthetic_study.compare_registered(db, user, state.settings, study_id, uuid4())
        model, _ = synthetic_study.register_model(db, user, state.settings, study_id, None, uuid4())
        synthetic_study.activate_model(db, user, state.settings, model.id, uuid4())
        return period, model.id, model.artifact_sha256, model.artifact_key


def real_counts(state, period_id):
    with state.owner.connect() as conn:
        return tuple(conn.execute(text("""SELECT
            (SELECT count(*) FROM risk_school.enrollments WHERE period_id=:p),
            (SELECT count(*) FROM risk_school.academic_snapshots WHERE period_id=:p),
            (SELECT count(*) FROM risk_school.risk_references WHERE period_id=:p),
            (SELECT count(*) FROM risk_school.predictions pr JOIN risk_school.enrollments e ON e.id=pr.enrollment_id WHERE e.period_id=:p),
            (SELECT count(*) FROM risk_school.alerts a JOIN risk_school.enrollments e ON e.id=a.enrollment_id WHERE e.period_id=:p),
            (SELECT string_agg(id::text||is_active::text, ',' ORDER BY id) FROM risk_school.model_versions WHERE data_origin='REAL')"""),
            {'p': period_id}).one())


def register(state, period_id, sha):
    with state.app.state.database.session_factory() as db:
        return demo_copy.register(db, admin(state, db), state.settings, UUID(str(period_id)), sha, uuid4())


def expect_code(code, function, *args):
    with pytest.raises(AppError) as error:
        function(*args)
    assert error.value.code == code, error.value.code


def demo_dates(state):
    with state.owner.connect() as conn:
        start, end = conn.execute(text('SELECT start_date,end_date FROM risk_school.academic_periods WHERE id=:p'), {'p': state.period_id}).one()
    cutoff = start + timedelta(days=40)
    assert cutoff + timedelta(days=17) <= end
    return start, cutoff


def enroll_and_measure(state, values, window, cutoff):
    student = write(state, '/students', dict(creation_key=str(uuid4()), anon_code='DEMO-' + uuid4().hex[:8], full_name='Estudiante Ficticio Demo',
                                             period_id=str(state.period_id), section_id=str(state.section_id))).json()
    body = dict(creation_key=str(uuid4()), window_start=window.isoformat(), cutoff_at=f'{cutoff.isoformat()}T18:00:00-05:00',
                available_at=f'{cutoff.isoformat()}T17:00:00-05:00', purpose='PARTIAL', participation_level=1,
                **dict(zip(FEATURES, values)))
    response = write(state, f"/students/{student['id']}/measurements?period_id={state.period_id}", body)
    assert response.status_code == 200, response.text
    assert 'participation_level' not in response.json()                                   # la respuesta nunca expone la participación
    return student


def test_demo_copy_of_the_real_svm_is_narrow_switchable_and_leaves_real_untouched(demo):
    state = demo
    period, real_id, sha, key = real_cycle(state)
    with state.app.state.database.session_factory() as db:
        demo_study = db.scalar(text('SELECT id FROM risk_school.synthetic_studies WHERE period_id=:p'), {'p': state.period_id})
    synthetic_model = state.model_id

    # --- Interruptor APAGADO (por defecto): nada cambia y la copia no se puede registrar.
    assert state.settings.demo_real_model_copy is False
    expect_code('DEMO_COPY_DISABLED', register, state, state.period_id, sha)
    with state.app.state.database.session_factory() as db:
        demo_period = db.get(AcademicPeriod, state.period_id)
        assert load_active_model(db, demo_period, state.settings, datetime.now(UTC))[1].id == synthetic_model

    with state.owner.connect() as conn:                                  # el periodo de demostración se llama DEMO-VIVO
        conn.execute(text("UPDATE risk_school.academic_periods SET code='DEMO-VIVO' WHERE id=:p"), {'p': state.period_id})
        conn.commit()

    # --- Interruptor ENCENDIDO: rechazos.
    state.settings.demo_real_model_copy = True
    try:
        expect_code('DEMO_COPY_PERIOD_INVALID', register, state, period['id'], sha)            # nunca en REAL-2026
        expect_code('DEMO_COPY_HASH_MISMATCH', register, state, state.period_id, '0' * 64)    # huella distinta a la del SVM REAL activo
        before = real_counts(state, period['id'])
        copy = register(state, state.period_id, sha)
        assert copy.data_origin == 'SYNTHETIC' and copy.is_active and copy.artifact_sha256 == sha and copy.artifact_key == key
        assert copy.manifest['demo_copy']['source_model_id'] == str(real_id) and copy.manifest['demo_copy']['source_data_origin'] == 'REAL'
        expect_code('DEMO_COPY_EXISTS', register, state, state.period_id, sha)                 # una sola copia por periodo
        with state.owner.connect() as conn:
            retired = conn.execute(text('SELECT status,is_active FROM risk_school.model_versions WHERE id=:m'), {'m': synthetic_model}).one()
            assert tuple(retired) == ('RETIRED', False)                                         # el sintético ya no evalúa ni se lista
            assert conn.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE action='DEMO_REAL_MODEL_COPY_REGISTERED' AND entity_id=:m"),
                               {'m': copy.id}) == 1
        listed = call(state, 'get', '/models?page=1&page_size=50').json()['items']
        assert str(synthetic_model) not in {item['id'] for item in listed}
        assert next(item for item in listed if item['id'] == str(copy.id))['display_label'] == 'SVM del estudio real'
        assert all(item['display_label'] is None for item in listed if item['id'] != str(copy.id))

        # La copia no sirve para ningún otro periodo; REAL-2026 conserva su SVM REAL.
        with state.app.state.database.session_factory() as db:
            real_study = db.get(SyntheticStudyRecord, db.get(ModelVersion, real_id).study_id)
            expect_code('DEMO_COPY_PERIOD_INVALID', demo_copy.verified_copy, db, state.settings, real_study, db.get(ModelVersion, copy.id))
            real_period = db.get(AcademicPeriod, UUID(period['id']))
            assert load_active_model(db, real_period, state.settings, datetime.now(UTC))[1].id == real_id

        # Tres casos: el nivel guardado es el que predice el SVM REAL activo; alerta solo para Medio y Alto.
        bundle = ArtifactStore(state.settings.ml_storage_dir).load(key)
        mapping = class_mapping(bundle.pipeline.classes_)
        window, cutoff = demo_dates(state)
        levels = {}
        for name, values in CASES.items():
            expected = mapping[bundle.pipeline.predict(pd.DataFrame([dict(zip(FEATURES, map(float, values)))], columns=list(bundle.config.features)))[0]]
            student = enroll_and_measure(state, values, window, cutoff)
            result = call(state, 'post', f"/students/{student['id']}/evaluate?period_id={state.period_id}")
            assert result.status_code == 200, result.text
            data = result.json()
            assert data['status'] == 'EVALUATED' and data['risk_level'] == expected
            assert (data['alert_id'] is not None) == (expected in ('MEDIUM', 'HIGH'))
            assert data['case_action'] == ('CREATED' if expected in ('MEDIUM', 'HIGH') else 'NONE')
            with state.owner.connect() as conn:
                stored = conn.execute(text('SELECT risk_level,model_id,data_origin FROM risk_school.predictions WHERE id=:i'),
                                      {'i': data['prediction_id']}).one()
                assert tuple(stored) == (expected, copy.id, 'SYNTHETIC')
            detail = call(state, 'get', f"/students/{student['id']}?period_id={state.period_id}").json()
            assert detail['latest_prediction']['model_id'] == str(copy.id) and 'participation_level' not in detail['latest_snapshot']
            assert detail['latest_prediction']['model_horizon_date'] is not None                  # mismo horizonte del SVM real
            assert 'participation_level' not in detail['latest_snapshot']['variable_available_at']
            page = call(state, 'get', f"/students/{student['id']}/measurements?period_id={state.period_id}").json()
            assert all('participation_level' not in item for item in page['items'])
            levels[name] = expected
        assert levels['HIGH'] == 'HIGH' and levels['LOW'] == 'LOW'                             # los extremos caen donde deben
        with state.owner.connect() as conn:
            assert conn.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE action='DEMO_REAL_MODEL_COPY_EVALUATED' AND entity_id=:m"),
                               {'m': copy.id}) == len(CASES)
        assert real_counts(state, period['id']) == before                                       # REAL-2026 intacto

        # --- Se APAGA de nuevo: la copia existente deja de reconocerse en las tres comprobaciones; nada se evalúa con ella.
        state.settings.demo_real_model_copy = False
        with state.app.state.database.session_factory() as db:
            copy_row, study = db.get(ModelVersion, copy.id), db.get(SyntheticStudyRecord, demo_study)
            expect_code('MODEL_INCOMPATIBLE', synthetic_study.compatible_model, state.settings, study, copy_row)
            # Igual que hoy con cualquier modelo que no cumple la procedencia del estudio del periodo.
            expect_code('MODEL_INCOMPATIBLE', load_active_model, db, db.get(AcademicPeriod, state.period_id), state.settings, datetime.now(UTC))
            assert load_active_model(db, db.get(AcademicPeriod, UUID(period['id'])), state.settings, datetime.now(UTC))[1].id == real_id
        student = enroll_and_measure(state, CASES['HIGH'], window, cutoff)
        refused = call(state, 'post', f"/students/{student['id']}/evaluate?period_id={state.period_id}")
        assert refused.status_code == 409 and refused.json()['code'] == 'MODEL_INCOMPATIBLE'
        assert real_counts(state, period['id']) == before
    finally:
        state.settings.demo_real_model_copy = False


def test_prediction_core_keeps_the_origin_rule_unless_the_demo_copy_is_explicit():
    from test_b4_institutional_ml import dataset
    from app.ml.institutional import compare_institutional
    built = dataset()
    result = compare_institutional(built, seed=0, study_id=uuid4(), repetitions=20)
    bundle = result.bundles['SVM']                                                   # artefacto REAL institucional (manifiesto v3)
    real_row = built.observations[0]
    synthetic = real_row.model_copy(update={'data_origin': 'SYNTHETIC'})
    assert predict_snapshot(real_row, bundle).status == 'EVALUATED'                  # su propio origen: sin cambios
    assert predict_snapshot(synthetic, bundle).status == 'INCOMPATIBLE'              # otro origen: rechazado como siempre
    assert predict_snapshot(synthetic, bundle, demo_copy=True).status == 'EVALUATED' # solo la copia explícita lo admite
    assert predict_snapshot(synthetic, bundle, demo_copy=True).risk_level == predict_snapshot(real_row, bundle).risk_level
    assert predict_snapshot(real_row, bundle, demo_copy=True).status == 'INCOMPATIBLE'   # la excepción es solo corte de demostración
