"""S3.1 against isolated PostgreSQL and the real API, never operational accounts.

The study is prepared explicitly by an authenticated fixture administrator. All
academic observations enter through preview/commit; there is no policy bypass.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import io
import json
import sys
import threading
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from conftest import create_context
from app.core.config import Settings
from app.core.errors import AppError
from app.models.s1 import AppUser
from app.models.ml import ModelVersion
from app.models.synthetic import SyntheticStudyRecord
from app.services import synthetic_study
from test_s1_schema import assert_sqlstate

API = '/api/v1'


def login_as(state, role):
    state.client.cookies.clear()
    account = state.context['accounts'][role]
    response = state.client.post(API + '/auth/login',
        json={'email': account['email'], 'password': account['password']},
        headers={'Origin': 'http://testserver'})
    assert response.status_code == 200, response.text
    state.csrf = response.json()['csrf_token']


@pytest.fixture
def study_env(owner_engine, database_urls, synthetic_password,
              synthetic_password_hash, tmp_path, monkeypatch, request):
    with owner_engine.begin() as connection:
        context = create_context(connection, synthetic_password, synthetic_password_hash)
    monkeypatch.setenv('DATABASE_URL', database_urls[0])
    monkeypatch.setenv('CSRF_SECRET', 's31-isolated-only-csrf-secret-at-least-32-bytes')
    monkeypatch.delenv('DATABASE_URL_FILE', raising=False)
    monkeypatch.delenv('CSRF_SECRET_FILE', raising=False)
    from app.main import create_app
    settings = Settings(app_env='test', database_url=database_urls[0],
        database_url_file=None, csrf_secret_file=None,
        csrf_secret='s31-isolated-only-csrf-secret-at-least-32-bytes',
        allowed_origins='http://testserver',
        import_storage_dir=tmp_path / 'imports', ml_storage_dir=tmp_path / 'ml')
    application = create_app(settings)
    with TestClient(application) as client:
        state = SimpleNamespace(client=client, app=application, settings=settings,
            context=context, owner=owner_engine,
            seed=int(hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:7], 16))
        login_as(state, 'ADMIN')
        yield state


def prepare(state, *, seed=None, config=None):
    from app.ml.synthetic import generate, load_config
    config = load_config(None) if config is None else config
    chosen_seed = state.seed if seed is None else seed
    generated = generate(config, chosen_seed)
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT current_user')) == 'riesgo_app'
        user = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        record, reused = synthetic_study.prepare(db, user, state.settings, config,
            chosen_seed, state.context['accounts']['TUTOR']['id'], uuid4())
        assert record.id == generated.study_id
    state.study_id, state.period_id, state.content = generated.study_id, generated.period_id, generated.csv_bytes
    state.config = config
    return reused


def preview(state, *, content=None, period_id=None, csrf=True):
    return state.client.post(API + '/imports/preview',
        data={'period_id': str(period_id or state.period_id)},
        files={'file': ('sintetico.csv', state.content if content is None else content, 'text/csv')},
        headers={'X-CSRF-Token': state.csrf} if csrf else {})


def commit(state, batch, *, client=None, version=None, csrf=True):
    return (client or state.client).post(API + f"/imports/{batch['id']}/commit",
        json={'expected_preview_version': batch['preview_version'] if version is None else version},
        headers={'X-CSRF-Token': state.csrf} if csrf else {})


def import_study(state):
    response = preview(state)
    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch['status'] == 'READY' and batch['data_origin'] == 'SYNTHETIC'
    assert commit(state, batch).status_code == 200
    return batch


def school_counts(state):
    with state.owner.connect() as connection:
        return {name: connection.scalar(text(f'SELECT count(*) FROM risk_school.{name}'))
            for name in ('students', 'enrollments', 'academic_snapshots', 'predictions')}


def test_preparation_is_explicit_idempotent_and_does_not_import(study_env):
    state = study_env
    before = school_counts(state)
    assert prepare(state) is False
    assert prepare(state) is True
    assert school_counts(state) == before
    with state.app.state.database.session_factory() as db:
        record = db.get(SyntheticStudyRecord, state.study_id)
        assert record.data_origin == 'SYNTHETIC' and not record.bindings and record.comparison is None
        assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='SYNTHETIC_STUDY_PREPARED'"), {'id': state.study_id}) == 1


def test_exact_csv_provenance_rejects_modification_and_wrong_context(study_env):
    state = study_env
    prepare(state)
    before = school_counts(state)
    changed = preview(state, content=state.content + b'\n')
    assert changed.status_code == 422 and changed.json()['code'] == 'UNREGISTERED_SYNTHETIC_FILE'
    wrong_context = preview(state, period_id=state.context['periods']['real']['id'])
    assert wrong_context.status_code == 422 and wrong_context.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    assert school_counts(state) == before and not state.settings.import_storage_dir.exists()
    malicious = state.client.post(API + '/imports/preview',
        data={'period_id': str(state.period_id), 'data_origin': 'SYNTHETIC'},
        files={'file': ('sintetico.csv', state.content, 'text/csv')},
        headers={'X-CSRF-Token': state.csrf})
    assert malicious.status_code == 422 and malicious.json()['code'] in {'INVALID_FORM', 'INVALID_MULTIPART'}


def test_preview_commit_bindings_repetition_and_no_false_consent(study_env):
    state = study_env
    prepare(state)
    before = school_counts(state)
    first = preview(state)
    assert first.status_code == 201, first.text
    batch = first.json()
    assert school_counts(state) == before
    assert state.client.get(API + f"/imports/{batch['id']}").json()['data_origin'] == 'SYNTHETIC'
    refreshed = preview(state).json()
    assert refreshed['id'] == batch['id'] and refreshed['preview_version'] == batch['preview_version'] + 1
    stale = commit(state, batch)
    assert stale.status_code == 409 and stale.json()['code'] == 'IMPORT_PREVIEW_STALE'
    assert school_counts(state) == before
    result = commit(state, refreshed)
    assert result.status_code == 200 and not result.json()['reused_result'], result.text
    count = state.config.student_count * (len(state.config.development_cutoffs) + len(state.config.external_cutoffs))
    assert result.json()['created_snapshots'] == count
    after = school_counts(state)
    assert after['students'] - before['students'] == state.config.student_count
    assert after['academic_snapshots'] - before['academic_snapshots'] == count
    assert commit(state, refreshed).json()['reused_result'] is True
    assert preview(state).json()['status'] == 'COMMITTED' and school_counts(state) == after
    with state.app.state.database.session_factory() as db:
        study = db.get(SyntheticStudyRecord, state.study_id)
        assert len(study.bindings) == count
        assert len({binding['snapshot_id'] for binding in study.bindings}) == count
        assert db.scalar(text("SELECT count(*) FROM risk_school.students s JOIN risk_school.enrollments e ON e.student_id=s.id WHERE e.period_id=:period AND s.eligible_for_processing AND NOT s.consent_documented AND NOT s.assent_documented"), {'period': state.period_id}) == state.config.student_count


def test_synthetic_commit_rollback_includes_bindings_and_audit(study_env, monkeypatch):
    state = study_env
    prepare(state)
    batch = preview(state).json()
    before = school_counts(state)
    original = synthetic_study.bind_imported
    def fail_after_binding(db, study, selected_batch, rows, settings):
        original(db, study, selected_batch, rows, settings)
        raise AppError(409, 'S31_ROLLBACK_PROBE', 'Fallo aislado después de vincular evidencia.')
    monkeypatch.setattr(synthetic_study, 'bind_imported', fail_after_binding)
    response = commit(state, batch)
    assert response.status_code == 409 and response.json()['code'] == 'S31_ROLLBACK_PROBE'
    assert school_counts(state) == before
    with state.app.state.database.session_factory() as db:
        assert db.get(SyntheticStudyRecord, state.study_id).bindings == []
        assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='IMPORT_COMMITTED'"), {'id': batch['id']}) == 0
    monkeypatch.setattr(synthetic_study, 'bind_imported', original)
    assert commit(state, batch).status_code == 200


def test_concurrent_confirmations_reuse_one_synthetic_import(study_env):
    state = study_env
    prepare(state)
    batch = preview(state).json()
    clients = [TestClient(state.app, cookies=state.client.cookies) for _ in range(2)]
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(commit, state, batch, client=client) for client in clients]
            responses = [future.result(timeout=30) for future in futures]
        assert all(response.status_code == 200 for response in responses), [r.text for r in responses]
        assert sorted(r.json()['reused_result'] for r in responses) == [False, True]
        with state.app.state.database.session_factory() as db:
            study = db.get(SyntheticStudyRecord, state.study_id)
            assert len(study.bindings) == batch['total_rows']
            assert db.scalar(text('SELECT count(*) FROM risk_school.academic_snapshots WHERE import_batch_id=:id'), {'id': batch['id']}) == batch['total_rows']
    finally:
        for client in clients:
            client.close()


def test_comparison_during_initial_commit_observes_no_partial_academic_evidence(study_env, monkeypatch):
    state = study_env
    from app.ml.synthetic import load_config
    config = load_config()
    # A predeclared closed calendar separates this study from the full-case
    # fixture. Seed, 60 students and all numeric assumptions stay unchanged.
    config = config.model_copy(update={'school_year': 2024,
        'period_start': config.period_start.replace(year=2024),
        'period_end': config.period_end.replace(year=2024),
        'fit_date': config.fit_date.replace(year=2024),
        'development_cutoffs': [cut.replace(year=2024) for cut in config.development_cutoffs],
        'external_cutoffs': [cut.replace(year=2024) for cut in config.external_cutoffs]})
    prepare(state, seed=1729, config=config)
    batch = preview(state).json()
    before = school_counts(state)
    importer_holds_period, release_import = threading.Event(), threading.Event()
    import_pid = {}
    original = synthetic_study.bind_imported

    def paused_binding(db, study, selected_batch, rows, settings):
        import_pid['value'] = db.scalar(text('SELECT pg_backend_pid()'))
        importer_holds_period.set()
        assert release_import.wait(15), 'The controlled import lock was not released'
        return original(db, study, selected_batch, rows, settings)

    def compare():
        with state.app.state.database.session_factory() as db:
            assert db.scalar(text('SELECT current_user')) == 'riesgo_app'
            actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
            try:
                return synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())
            except AppError as error:
                return error

    monkeypatch.setattr(synthetic_study, 'bind_imported', paused_binding)
    client = TestClient(state.app, cookies=state.client.cookies)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            importing = executor.submit(commit, state, batch, client=client)
            assert importer_holds_period.wait(10)
            try:
                with state.owner.connect() as observer:
                    assert observer.scalar(text("""SELECT EXISTS(SELECT 1 FROM pg_locks
                        WHERE pid=:pid AND relation='risk_school.academic_periods'::regclass
                        AND mode='RowShareLock' AND granted)"""), {'pid': import_pid['value']})
                result = executor.submit(compare).result(timeout=10)
                assert isinstance(result, AppError)
                assert result.status_code == 409 and result.code == 'SYNTHETIC_IMPORT_REQUIRED'
                assert school_counts(state) == before
                assert not list(state.settings.ml_storage_dir.glob('*/pipeline.joblib'))
                with state.app.state.database.session_factory() as db:
                    study = db.get(SyntheticStudyRecord, state.study_id)
                    assert not study.bindings and study.comparison is None
                    assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='SYNTHETIC_MODELS_COMPARED'"), {'id': state.study_id}) == 0
            finally:
                release_import.set()
            response = importing.result(timeout=30)
        assert response.status_code == 200, response.text
        report = compare()
        assert isinstance(report, dict), getattr(report, 'code', 'unexpected comparison output')
        assert report['scope'] == 'SYNTHETIC_STUDY' and not report['reused']
        with state.app.state.database.session_factory() as db:
            study = db.get(SyntheticStudyRecord, state.study_id)
            assert len(study.bindings) == batch['total_rows'] and study.comparison
            assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='IMPORT_COMMITTED'"), {'id': batch['id']}) == 1
            assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='SYNTHETIC_MODELS_COMPARED'"), {'id': state.study_id}) == 1
    finally:
        release_import.set()
        client.close()


def test_roles_csrf_and_general_processing_status(study_env):
    state = study_env
    state.client.cookies.clear()
    assert state.client.get(API + '/processing/status').status_code == 401
    login_as(state, 'ADMIN')
    prepare(state)
    assert preview(state, csrf=False).status_code == 403
    batch = preview(state).json()
    assert commit(state, batch, csrf=False).status_code == 403
    for role in ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'):
        login_as(state, role)
        response = state.client.get(API + '/processing/status')
        assert response.status_code == 200, response.text
        status = response.json()
        assert status['scope'] == 'SYNTHETIC_STUDY' and not status['institutional_ready']
        assert status['synthetic_ready']
        assert status['operations']['import']['available'] is (role == 'ADMIN')
        assert not {'period_id', 'study_id', 'artifact_key', 'labels', 'partitions', 'metrics'} & set(status)
        if role != 'ADMIN':
            assert preview(state).status_code == 403
            assert commit(state, batch).status_code == 403
            with state.app.state.database.session_factory() as db:
                actor = db.get(AppUser, state.context['accounts'][role]['id'])
                with pytest.raises(AppError) as caught:
                    synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())
                assert caught.value.code == 'FORBIDDEN'
        if role == 'RESEARCHER':
            assert not any(operation['available'] for operation in status['operations'].values())
            assert state.client.get(API + '/students', params={'period_id': str(state.period_id)}).status_code == 403


def test_unimported_study_cannot_compare_or_register(study_env):
    state = study_env
    prepare(state)
    with state.app.state.database.session_factory() as db:
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        with pytest.raises(AppError) as caught:
            synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())
        assert caught.value.code == 'SYNTHETIC_IMPORT_REQUIRED'
        with pytest.raises(AppError) as caught:
            synthetic_study.register_model(db, actor, state.settings, state.study_id, None, uuid4())
        assert caught.value.code == 'SYNTHETIC_COMPARISON_REQUIRED'


@pytest.mark.parametrize('diagnostic,expected_code', [
    ('INSUFFICIENT_CLASS_GROUP_SUPPORT', 'INSUFFICIENT_CLASS_GROUP_SUPPORT'),
    ('private-file C:\\private\\students.csv password=PRIVATE-SENTINEL', 'ML_DIAGNOSTIC'),
])
def test_authenticated_cli_ml_diagnostics_are_explicit_and_sanitized(
        study_env, monkeypatch, capsys, diagnostic, expected_code):
    state = study_env
    prepare(state)
    from app import synthetic_cli
    from app.core.database import Database
    from app.ml.features import MLDiagnostic
    actor_id = state.context['accounts']['ADMIN']['id']
    account = state.context['accounts']['ADMIN']
    before = school_counts(state)
    with state.app.state.database.session_factory() as db:
        before_audit = db.scalar(text('SELECT count(*) FROM risk_school.audit_events'))
        before_models = db.scalar(text('SELECT count(*) FROM risk_school.model_versions'))
    authenticated = []

    def diagnostic_after_authentication(db, actor, settings, study_id, request_id):
        assert db.scalar(text('SELECT current_user')) == 'riesgo_app'
        assert actor.id == actor_id and actor.role == 'ADMIN' and actor.is_active
        assert study_id == state.study_id
        authenticated.append(actor.id)
        raise MLDiagnostic(diagnostic)

    monkeypatch.setattr(synthetic_cli, 'Settings', lambda: state.settings)
    # A real, separately disposable application-role engine reads the fixture
    # account. Neither password verification nor authorization is replaced.
    monkeypatch.setattr(synthetic_cli, 'Database', lambda settings: Database(settings))
    monkeypatch.setattr(synthetic_study, 'compare_registered', diagnostic_after_authentication)
    monkeypatch.setattr(sys, 'argv', ['synthetic_cli', 'compare'])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({
        'email': account['email'], 'password': account['password'],
        'study_id': str(state.study_id)})))
    capsys.readouterr()
    assert synthetic_cli.main() == 2
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert authenticated == [actor_id]
    assert output['code'] == expected_code and isinstance(output['message'], str)
    assert set(output) == {'code', 'message'} and not captured.err
    assert not any(private in captured.out for private in (
        account['password'], account['email'], 'PRIVATE-SENTINEL',
        'C:\\private', 'students.csv', 'Traceback', 'SELECT', 'student_code'))
    assert school_counts(state) == before
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT count(*) FROM risk_school.audit_events')) == before_audit
        assert db.scalar(text('SELECT count(*) FROM risk_school.model_versions')) == before_models
        study = db.get(SyntheticStudyRecord, state.study_id)
        assert study.comparison is None and not study.bindings


def test_processing_status_tutor_without_synthetic_section(study_env):
    state = study_env
    prepare(state)
    tutor_id = state.context['accounts']['TUTOR']['id']
    with state.app.state.database.session_factory() as db:
        db.execute(text('UPDATE risk_school.grade_sections SET tutor_id=NULL WHERE tutor_id=:tutor AND school_year=:year'),
            {'tutor': tutor_id, 'year': state.config.school_year})
        db.commit()
    login_as(state, 'TUTOR')
    response = state.client.get(API + '/processing/status')
    assert response.status_code == 200
    status = response.json()
    assert status['synthetic_ready'] and not status['institutional_ready']
    assert status['operations']['read_students']['available'] is False
    periods = state.client.get(API + '/periods')
    assert periods.status_code == 200
    assert str(state.period_id) not in {period['id'] for period in periods.json()}
    assert state.client.get(API + '/students', params={'period_id': str(state.period_id)}).status_code == 403


def test_synthetic_and_real_catalogs_do_not_mix_sections_in_same_year(study_env):
    state = study_env
    prepare(state)
    from app.configure_context import configure, PeriodInput, SectionInput
    with state.app.state.database.session_factory() as db:
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        real_period = configure(db, actor, PeriodInput(code='REAL-' + uuid4().hex[:12],
            school_year=state.config.school_year, start_date=state.config.period_start,
            end_date=state.config.period_end))
        real_section = configure(db, actor, SectionInput(code='REAL-' + uuid4().hex[:12],
            school_year=state.config.school_year, grade=1,
            tutor_id=state.context['accounts']['TUTOR']['id']))
    synthetic_sections = state.client.get(API + '/sections', params={'period_id': str(state.period_id)})
    real_sections = state.client.get(API + '/sections', params={'period_id': str(real_period)})
    assert synthetic_sections.status_code == real_sections.status_code == 200
    synthetic_ids = {section['id'] for section in synthetic_sections.json()}
    real_ids = {section['id'] for section in real_sections.json()}
    assert len(synthetic_ids) == 2 and str(real_section) in real_ids
    assert synthetic_ids.isdisjoint(real_ids)
    login_as(state, 'TUTOR')
    own_synthetic = state.client.get(API + '/sections', params={'period_id': str(state.period_id)})
    own_real = state.client.get(API + '/sections', params={'period_id': str(real_period)})
    assert own_synthetic.status_code == own_real.status_code == 200
    assert len(own_synthetic.json()) == 1
    assert synthetic_ids.isdisjoint(section['id'] for section in own_real.json())


def test_private_registered_payload_corruption_is_rejected(study_env):
    state = study_env
    prepare(state)
    with state.app.state.database.session_factory() as db:
        study = db.get(SyntheticStudyRecord, state.study_id)
        path = state.settings.ml_storage_dir / 'studies' / study.storage_key
    path.write_bytes(b'{"scope":"SYNTHETIC_STUDY"}')
    before = school_counts(state)
    response = preview(state)
    assert response.status_code == 409 and response.json()['code'] == 'STUDY_INTEGRITY_ERROR'
    assert school_counts(state) == before
    status = state.client.get(API + '/processing/status').json()
    assert status['synthetic_ready'] is False


def test_registered_database_evidence_is_immutable(study_env):
    state = study_env
    prepare(state)
    import_study(state)
    with state.app.state.database.session_factory() as db:
        for statement in (
            "UPDATE risk_school.synthetic_studies SET seed=seed+1 WHERE id=:id",
            "UPDATE risk_school.synthetic_studies SET bindings='[]'::jsonb WHERE id=:id",
        ):
            assert_sqlstate(db, statement, {'id': state.study_id}, '55000')
        assert db.scalar(text("SELECT has_table_privilege(current_user,'risk_school.synthetic_studies','DELETE')")) is False
        assert db.scalar(text("SELECT has_table_privilege(current_user,'risk_school.synthetic_studies','TRUNCATE')")) is False


def test_database_origin_links_and_exact_registered_hash(study_env):
    state = study_env
    prepare(state)
    import_study(state)
    with state.app.state.database.session_factory() as db:
        own = db.execute(text('SELECT student_id,section_id FROM risk_school.enrollments WHERE period_id=:period LIMIT 1'), {'period': state.period_id}).mappings().one()
        assert_sqlstate(db,
            "INSERT INTO risk_school.enrollments(student_id,period_id,section_id,data_origin) VALUES(:student,:period,:section,'SYNTHETIC')",
            {'student': own['student_id'], 'period': state.context['periods']['real']['id'], 'section': own['section_id']}, '23503')
        assert_sqlstate(db,
            "INSERT INTO risk_school.import_batches(period_id,data_origin,created_by,file_name,file_sha256,storage_key,study_id) VALUES(:period,'SYNTHETIC',:actor,'fixture.csv',repeat('f',64),'fixture.csv',:study)",
            {'period': state.period_id, 'actor': state.context['accounts']['ADMIN']['id'], 'study': state.study_id}, '23503')
        assert_sqlstate(db,
            "INSERT INTO risk_school.model_versions(name,version,algorithm,data_origin,dataset_hash,artifact_sha256,artifact_key,feature_schema_version,reference_criterion_version,status,parameters,metrics,manifest,study_id) VALUES(:name,'fixture','DUMMY','REAL',repeat('0',64),repeat('0',64),'fixture','ml-features-v1','fixture','EVALUATED','{}','{}','{}',:study)",
            {'name': str(uuid4()), 'study': state.study_id}, '23514')


def inactive_model(state, db, *, origin='SYNTHETIC', study_id=None, manifest=None):
    record = ModelVersion(name='S31 isolated fixture ' + uuid4().hex, version='fixture',
        algorithm='DUMMY', data_origin=origin, study_id=(study_id or state.study_id) if origin == 'SYNTHETIC' else None,
        dataset_hash='0' * 64, artifact_sha256='0' * 64, artifact_key=uuid4().hex,
        feature_schema_version='ml-features-v1', reference_criterion_version='fixture',
        status='APPROVED', is_active=False, parameters={}, metrics={}, manifest=manifest or {})
    db.add(record)
    db.flush()
    return record


def test_database_activation_rejects_real_and_incomplete_synthetic_manifest(study_env):
    state = study_env
    prepare(state)
    with state.app.state.database.session_factory() as db:
        real = inactive_model(state, db, origin='REAL')
        synthetic = inactive_model(state, db)
        for record in (real, synthetic):
            assert_sqlstate(db, 'UPDATE risk_school.model_versions SET is_active=true WHERE id=:id', {'id': record.id}, '23514')
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        with pytest.raises(AppError) as caught:
            synthetic_study.activate_model(db, actor, state.settings, real.id, uuid4())
        assert caught.value.code == 'INSTITUTIONAL_PROCESSING_NOT_READY'
        with pytest.raises(AppError) as caught:
            synthetic_study.activate_model(db, actor, state.settings, synthetic.id, uuid4())
        assert caught.value.code == 'MODEL_INCOMPATIBLE'
        db.rollback()


def test_prediction_database_rejects_other_synthetic_study(study_env):
    state = study_env
    prepare(state)
    first_study, first_period = state.study_id, state.period_id
    import_study(state)
    prepare(state, seed=state.seed + 1)
    with state.app.state.database.session_factory() as db:
        wrong = inactive_model(state, db)
        snapshot = db.execute(text('SELECT id,enrollment_id FROM risk_school.academic_snapshots WHERE period_id=:period LIMIT 1'), {'period': first_period}).mappings().one()
        assert wrong.study_id != first_study
        assert_sqlstate(db,
            "INSERT INTO risk_school.predictions(snapshot_id,enrollment_id,model_id,data_origin,risk_level) VALUES(:snapshot,:enrollment,:model,'SYNTHETIC','HIGH')",
            {'snapshot': snapshot['id'], 'enrollment': snapshot['enrollment_id'], 'model': wrong.id}, '23514')
        db.rollback()


def test_full_registered_comparison_activation_and_api_inference(study_env):
    state = study_env
    # The protocol's declared example seed is fixed before evaluating metrics.
    prepare(state, seed=1729)
    import_study(state)
    with state.app.state.database.session_factory() as db:
        actor = db.get(AppUser, state.context['accounts']['ADMIN']['id'])
        report = synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())
        assert report['scope'] == 'SYNTHETIC_STUDY' and report['reused'] is False
        assert synthetic_study.compare_registered(db, actor, state.settings, state.study_id, uuid4())['reused'] is True
        selected = db.get(SyntheticStudyRecord, state.study_id).comparison['selected_algorithm']
        alternative = next(algorithm for algorithm in ('DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST') if algorithm != selected)
        with pytest.raises(AppError) as caught:
            synthetic_study.register_model(db, actor, state.settings, state.study_id, alternative, uuid4())
        assert caught.value.status_code == 422 and caught.value.code == 'MODEL_NOT_SELECTED'
        assert db.scalar(text('SELECT count(*) FROM risk_school.model_versions WHERE study_id=:study'), {'study': state.study_id}) == 0
        model, reused = synthetic_study.register_model(db, actor, state.settings, state.study_id, None, uuid4())
        assert not reused and not model.is_active and model.data_origin == 'SYNTHETIC'
        identifier = model.id
        assert synthetic_study.register_model(db, actor, state.settings, state.study_id, None, uuid4())[1] is True
        activated, reused = synthetic_study.activate_model(db, actor, state.settings, identifier, uuid4())
        assert activated.is_active and not reused
        assert synthetic_study.activate_model(db, actor, state.settings, identifier, uuid4())[1] is True
        assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE action='SYNTHETIC_MODEL_ACTIVATED' AND payload->>'model_id'=:id"), {'id': str(identifier)}) == 1
    detail = state.client.get(API + f'/models/{identifier}')
    assert detail.status_code == 200 and detail.json()['is_active']
    assert not {'artifact_key', 'manifest', 'labels', 'dataset_hash', 'metrics', 'parameters'} & set(detail.json())
    model_ids = {record['id'] for record in state.client.get(API + '/models', params={'page_size': 100}).json()['items']}
    assert str(identifier) in model_ids
    payload = {'period_id': str(state.period_id), 'as_of': datetime.now(UTC).isoformat()}
    assert state.client.post(API + '/predictions/run', json=payload).status_code == 403
    # Both requests begin together and use independent HTTP clients/connections.
    # The unique(snapshot,model) constraint decides the winning insertion.
    clients = [TestClient(state.app, cookies=state.client.cookies) for _ in range(2)]
    barrier = threading.Barrier(2)
    def run(client):
        barrier.wait(timeout=10)
        return client.post(API + '/predictions/run', json=payload,
            headers={'X-CSRF-Token': state.csrf})
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = [future.result(timeout=60) for future in
                [executor.submit(run, client) for client in clients]]
        assert all(response.status_code == 200 for response in responses), [response.text for response in responses]
        outcomes = [response.json() for response in responses]
    finally:
        for client in clients:
            client.close()
    outcome = outcomes[0]
    assert outcome['selected'] == state.config.student_count
    assert all(result['selected'] == outcome['selected'] and result['abstentions'] == outcome['abstentions'] for result in outcomes)
    evaluated_count = sum(result['created'] for result in outcomes)
    assert evaluated_count > 0 and outcome['abstentions']
    assert sum(result['reused'] for result in outcomes) == evaluated_count
    assert evaluated_count + len(outcome['abstentions']) == outcome['selected']
    with state.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT count(*) FROM risk_school.predictions WHERE model_id=:model'), {'model': identifier}) == evaluated_count
        audit_count = db.execute(text("SELECT count(*),count(DISTINCT entity_id) FROM risk_school.audit_events WHERE action='PREDICTION_CREATED' AND payload->>'model_id'=:model"), {'model': str(identifier)}).one()
        assert tuple(audit_count) == (evaluated_count, evaluated_count)
    repeated = state.client.post(API + '/predictions/run', json=payload, headers={'X-CSRF-Token': state.csrf})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()['created'] == 0 and repeated.json()['reused'] == evaluated_count
    real_attempt = state.client.post(API + '/predictions/run', json={
        **payload, 'period_id': str(state.context['periods']['real']['id'])},
        headers={'X-CSRF-Token': state.csrf})
    assert real_attempt.status_code == 422 and real_attempt.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    listing = state.client.get(API + '/students', params={'period_id': str(state.period_id), 'page_size': 100})
    assert listing.status_code == 200 and listing.json()['total'] == state.config.student_count
    records = listing.json()['items']
    assert all(student['data_origin'] == 'SYNTHETIC' for student in records)
    insufficient = [student for student in records if student['risk_level'] is None]
    assert len(insufficient) == len(outcome['abstentions'])
    assert all(student['evaluation_status'] == 'INSUFFICIENT_DATA' for student in insufficient)
    insufficient_detail = state.client.get(API + f"/students/{insufficient[0]['id']}",
        params={'period_id': str(state.period_id)})
    assert insufficient_detail.status_code == 200
    assert insufficient_detail.json()['student']['evaluation_status'] == 'INSUFFICIENT_DATA'
    assert insufficient_detail.json()['latest_prediction'] is None
    first = next(student for student in records if student['risk_level'] is not None)
    student_detail = state.client.get(API + f"/students/{first['id']}", params={'period_id': str(state.period_id)})
    assert student_detail.status_code == 200
    prediction = student_detail.json()['latest_prediction']
    assert prediction and prediction['data_origin'] == 'SYNTHETIC'
    assert prediction['probabilities_calibrated'] is False
    assert all(prediction[name] is None for name in ('probability_low', 'probability_medium', 'probability_high'))
    timeline = state.client.get(API + f"/students/{first['id']}/timeline", params={'period_id': str(state.period_id)})
    assert timeline.status_code == 200 and any(event['event_type'] == 'PREDICTION' for event in timeline.json()['items'])
    prediction_id = prediction['id']
    for role in ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'):
        login_as(state, role)
        rows = state.client.get(API + '/students', params={'period_id': str(state.period_id), 'page_size': 100})
        if role == 'RESEARCHER':
            assert rows.status_code == 403
            assert state.client.get(API + f'/predictions/{prediction_id}').status_code == 403
        else:
            assert rows.status_code == 200
            assert rows.json()['total'] == (state.config.student_count // 2 if role == 'TUTOR' else state.config.student_count)
    login_as(state, 'TUTOR')
    own = state.client.get(API + '/students', params={'period_id': str(state.period_id), 'page_size': 100}).json()['items']
    own_ids = {student['id'] for student in own}
    own_evaluated = next(student for student in own if student['risk_level'] is not None)
    own_detail = state.client.get(API + f"/students/{own_evaluated['id']}", params={'period_id': str(state.period_id)})
    assert own_detail.status_code == 200
    own_prediction = own_detail.json()['latest_prediction']['id']
    assert state.client.get(API + f'/predictions/{own_prediction}').status_code == 200
    foreign = next(student for student in records if student['id'] not in own_ids and student['risk_level'] is not None)
    login_as(state, 'ADMIN')
    foreign_prediction = state.client.get(API + f"/students/{foreign['id']}", params={'period_id': str(state.period_id)}).json()['latest_prediction']['id']
    login_as(state, 'TUTOR')
    assert state.client.get(API + f'/predictions/{foreign_prediction}').status_code == 404
    assert state.client.get(API + f'/predictions/{uuid4()}').status_code == 404
    assert state.client.post(API + '/predictions/run', json=payload, headers={'X-CSRF-Token': state.csrf}).status_code == 403
    login_as(state, 'ADMIN')
    with state.app.state.database.session_factory() as db:
        model = db.get(ModelVersion, identifier)
        artifact_path = state.settings.ml_storage_dir / model.artifact_key / 'pipeline.joblib'
    artifact_path.write_bytes(b'corrupted isolated artifact')
    before = school_counts(state)
    processing = state.client.get(API + '/processing/status').json()
    assert processing['operations']['predict']['available'] is False
    assert processing['operations']['register']['available'] is False
    assert processing['operations']['activate']['available'] is False
    unavailable = state.client.post(API + '/predictions/run', json=payload,
        headers={'X-CSRF-Token': state.csrf})
    assert unavailable.status_code == 409 and unavailable.json()['code'] == 'MODEL_NOT_AVAILABLE'
    assert school_counts(state) == before
