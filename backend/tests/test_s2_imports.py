"""S2 contra PostgreSQL real: cada petición usa riesgo_app y transacciones propias."""
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import UTC, datetime
import io
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from conftest import create_context
from app.core.config import Settings
from app.models.s1 import AuditEvent
from app.services.csv_validation import HEADERS, MAX_BYTES

API = '/api/v1'
SAMPLES = []


@pytest.fixture(scope='module', autouse=True)
def write_contract_samples():
    yield
    directory = Path('/evidence') if Path('/evidence').exists() else Path('tests/evidence')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (os.environ.get('TEST_REPORT_NAME', 's3-1-backend').removesuffix('-backend') + '-response-samples.json')).write_text(json.dumps(SAMPLES, indent=2) + '\n', encoding='utf-8')


def sample(schema, body):
    SAMPLES.append({'schema': schema, 'body': body})


@pytest.fixture
def env(owner_engine, database_urls, synthetic_password, synthetic_password_hash, tmp_path, monkeypatch):
    from app.services import imports as import_service
    monkeypatch.setattr(import_service, 'require_processing_protocol', lambda: None)
    with owner_engine.begin() as connection:
        context = create_context(connection, synthetic_password, synthetic_password_hash)
    monkeypatch.setenv('DATABASE_URL', database_urls[0])
    monkeypatch.setenv('CSRF_SECRET', 'isolated-s2-tests-csrf-secret-at-least-32-bytes')
    monkeypatch.delenv('DATABASE_URL_FILE', raising=False)
    monkeypatch.delenv('CSRF_SECRET_FILE', raising=False)
    from app.main import create_app
    app = create_app(Settings(database_url=database_urls[0], csrf_secret='isolated-s2-tests-csrf-secret-at-least-32-bytes',
        allowed_origins='http://testserver', import_storage_dir=tmp_path / 'private-imports', app_env='test'))
    with app.state.database.engine.connect() as conn:
        assert conn.scalar(text('SELECT current_user')) == 'riesgo_app'
    with TestClient(app) as client:
        result = SimpleNamespace(client=client, app=app, context=context, owner=owner_engine,
            directory=tmp_path / 'private-imports', prefix='S2-' + uuid4().hex[:12])
        login_as(result, 'ADMIN')
        yield result


def login_as(env, role):
    account = env.context['accounts'][role]
    env.client.cookies.clear()
    response = env.client.post(API + '/auth/login', json={'email': account['email'], 'password': account['password']},
                               headers={'Origin': 'http://testserver'})
    assert response.status_code == 200
    env.csrf = response.json()['csrf_token']


def row(env, **overrides):
    return {**dict(zip(HEADERS, [env.prefix, '1', env.context['sections'][0]['code'],
        '2026-05-01T23:30:00-05:00', '2026-05-02', '2026-05-01T18:00:00-05:00', '2026-04-01',
        '14.25', '90.50', '', '2', '0', '13'], strict=True)), **overrides}


def csv_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=HEADERS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def preview(env, rows=None, *, content=None, period=None, csrf=True, filename='sintetico.csv'):
    return env.client.post(API + '/imports/preview', data={'period_id': str(period or env.context['periods']['demo']['id'])},
        files={'file': (filename, content if content is not None else csv_bytes(rows or [row(env)]), 'text/csv')},
        headers={'X-CSRF-Token': env.csrf} if csrf else {})


def commit(env, batch, *, version=None, csrf=True, client=None):
    return (client or env.client).post(API + f"/imports/{batch['id']}/commit",
        json={'expected_preview_version': batch['preview_version'] if version is None else version},
        headers={'X-CSRF-Token': env.csrf} if csrf else {})


def counts(env):
    with env.owner.connect() as connection:
        return {table: connection.scalar(text(f'SELECT count(*) FROM risk_school.{table}'))
                for table in ['students', 'enrollments', 'academic_snapshots', 'audit_events']}


def assert_preview(response):
    assert response.status_code in (200, 201), response.text
    body = response.json()
    assert body['status'] == 'READY', body
    return body


def test_valid_preview_commit_and_private_storage(env):
    before = counts(env)
    batch = assert_preview(preview(env, filename='../../sintetico.csv'))
    sample('ImportBatch', batch)
    after = counts(env)
    for key in ['students', 'enrollments', 'academic_snapshots']:
        assert after[key] == before[key]
    assert (batch['planned_students'], batch['planned_enrollments'], batch['planned_snapshots']) == (1, 1, 1)
    assert batch['file_name'] == 'sintetico.csv'
    assert set(batch).isdisjoint({'storage_key', 'preview_state', 'created_by'})
    saved = list(env.directory.glob('*.csv'))
    assert len(saved) == 1 and saved[0].name == batch['id'].replace('-', '') + '.csv'
    assert saved[0].read_bytes() == csv_bytes([row(env)])
    if os.name != 'nt':
        assert saved[0].stat().st_mode & 0o777 == 0o600
    result = commit(env, batch)
    assert result.status_code == 200, result.text
    assert result.json()['created_snapshots'] == 1 and result.json()['reused_result'] is False
    sample('ImportCommit', result.json())
    detail = env.client.get(API + f"/imports/{batch['id']}")
    assert detail.json()['status'] == 'COMMITTED'
    assert detail.json()['committed_at'].endswith('Z')
    with env.owner.connect() as conn:
        snapshot = conn.execute(text('SELECT * FROM risk_school.academic_snapshots WHERE import_batch_id=:id'), {'id': batch['id']}).mappings().one()
        assert snapshot['cutoff_at'] == datetime(2026, 5, 2, 4, 30, tzinfo=UTC)
        assert str(snapshot['target_date']) == '2026-05-02'  # Día Lima, aunque UTC ya sea 2.
        assert snapshot['activities_pct'] is None and float(snapshot['missing_fraction']) == 0.1667
        assert snapshot['revision'] == 1 and snapshot['supersedes_id'] is None
        assert conn.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE entity_id=:id AND action='IMPORT_COMMITTED'"), {'id': batch['id']}) == 1


@pytest.mark.parametrize('field,value', [
    ('average_grade', '20.001'), ('average_grade', 'NaN'), ('attendance_pct', '1e2'), ('attendance_pct', '100.01'),
    ('activities_pct', '-1'), ('participation_level', '4'), ('behavior_incidents', '2147483648'), ('age_years', '4'),
    ('age_years', '13.0'), ('grade', '6'), ('section', 'AJENA'), ('student_code', 'xx'),
    ('cutoff_at', '2026-05-01T10:00:00'), ('available_at', '2026-05-02T04:30:01Z'),
    ('window_start', '2025-12-31'), ('window_start', '2026-05-02'), ('target_date', '2026-05-01'),
    ('target_date', '2027-01-01'), ('target_date', '2026-02-30'),
])
def test_invalid_rows_cannot_commit(env, field, value):
    before = counts(env)
    response = preview(env, [row(env, **{field: value})])
    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch['status'] == 'FAILED' and batch['invalid_rows'] == 1
    assert all(e['row'] == 2 and e['column'] and e['message'] for e in batch['errors'])
    denied = commit(env, batch)
    assert denied.status_code == 422 and denied.json()['code'] == 'IMPORT_INVALID'
    after = counts(env)
    for key in ['students', 'enrollments', 'academic_snapshots']:
        assert after[key] == before[key]
    if field == 'average_grade' and value == '20.001':
        sample('ImportBatch', batch)
        sample('Error', denied.json())


@pytest.mark.parametrize('kind,code', [('utf8','CSV_ENCODING'), ('header','CSV_HEADERS'), ('duplicate_header','CSV_HEADERS'),
                                      ('large','CSV_TOO_LARGE'), ('huge','CSV_TOO_LARGE'), ('rows','CSV_TOO_MANY_ROWS')])
def test_file_limits_and_headers(env, kind, code):
    content = csv_bytes([row(env)])
    if kind == 'utf8': content += b'\xff'
    if kind == 'header': content = content.replace(b'student_code', b'risk_level', 1)
    if kind == 'duplicate_header': content = content.replace(b'grade,section', b'grade,grade', 1)
    if kind == 'large': content = b'x' * (MAX_BYTES + 1)
    if kind == 'huge': content = b'x' * (MAX_BYTES + 100000)
    if kind == 'rows': content = csv_bytes([row(env)] * 10001)
    response = preview(env, content=content)
    assert response.status_code == 422 and response.json()['code'] == code
    assert response.json()['details'][0]['row'] >= 1
    assert not env.directory.exists()


def test_duplicates_normalize_utc_and_do_not_partially_import(env):
    response = preview(env, [row(env), row(env, cutoff_at='2026-05-02T04:30:00Z'), row(env, student_code=env.prefix + '-OK')])
    batch = response.json()
    assert response.status_code == 201 and batch['invalid_rows'] == 2 and batch['valid_rows'] == 1
    assert {e['row'] for e in batch['errors'] if e['code'] == 'DUPLICATE_ROW'} == {2, 3}
    before = counts(env)
    assert commit(env, batch).status_code == 422
    assert counts(env) == before


def test_empty_values_remain_null_and_empty_file_is_invalid(env):
    batch = assert_preview(preview(env, [row(env, **{k: '' for k in HEADERS[7:]})]))
    assert commit(env, batch).status_code == 200
    with env.owner.connect() as conn:
        snapshot = conn.execute(text('SELECT * FROM risk_school.academic_snapshots WHERE import_batch_id=:id'), {'id': batch['id']}).mappings().one()
        assert all(snapshot[k] is None for k in HEADERS[7:]) and snapshot['missing_fraction'] == 1
    empty = preview(env, content=csv_bytes([])).json()
    assert empty['total_rows'] == 0 and empty['status'] == 'FAILED'
    assert commit(env, empty).status_code == 422


def test_repeat_refresh_old_version_and_committed_reuse_even_locked(env):
    content = csv_bytes([row(env)])
    first = assert_preview(preview(env, content=content))
    refreshed = assert_preview(preview(env, content=content))
    assert refreshed['id'] == first['id'] and refreshed['preview_version'] == 2
    assert commit(env, first).json()['code'] == 'IMPORT_PREVIEW_STALE'
    assert commit(env, refreshed).status_code == 200
    before = counts(env)
    with env.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.academic_periods SET is_locked=true WHERE id=:id'), {'id': first['period_id']})
    repeated = commit(env, first)
    assert repeated.status_code == 200 and repeated.json()['reused_result'] is True
    again = preview(env, content=content)
    assert again.status_code == 200 and again.json()['preview_version'] == 2
    assert counts(env) == before


def test_correction_creates_immutable_revision_and_equivalent_rows_reuse(env):
    first = assert_preview(preview(env))
    assert commit(env, first).status_code == 200
    second = assert_preview(preview(env, [row(env, average_grade='16.00')]))
    assert second['planned_students'] == second['planned_enrollments'] == 0
    assert second['planned_snapshots'] == 1
    assert commit(env, second).status_code == 200
    equivalent = assert_preview(preview(env, [row(env, average_grade='16', cutoff_at='2026-05-02T04:30:00Z')]))
    assert equivalent['planned_snapshots'] == 0
    assert commit(env, equivalent).json()['created_snapshots'] == 0
    with env.owner.connect() as conn:
        snapshots = conn.execute(text('SELECT id,revision,supersedes_id,average_grade FROM risk_school.academic_snapshots WHERE import_batch_id IN (:a,:b) ORDER BY revision'), {'a': first['id'], 'b': second['id']}).mappings().all()
        assert [s['revision'] for s in snapshots] == [1, 2]
        assert snapshots[1]['supersedes_id'] == snapshots[0]['id']
        assert float(snapshots[0]['average_grade']) == 14.25


def test_period_dates_changed_and_enrollment_section_conflict(env):
    batch = assert_preview(preview(env))
    with env.owner.begin() as conn:
        conn.execute(text("UPDATE risk_school.academic_periods SET start_date='2026-04-15' WHERE id=:id"), {'id': batch['period_id']})
    denied = commit(env, batch)
    assert denied.status_code == 409 and denied.json()['code'] == 'IMPORT_PREVIEW_STALE'
    refreshed = assert_preview(preview(env, [row(env, window_start='2026-04-20')]))
    assert commit(env, refreshed).status_code == 200
    conflict = preview(env, [row(env, window_start='2026-04-20', grade='2')]).json()
    assert any(e['code'] == 'ENROLLMENT_SECTION_CONFLICT' for e in conflict['errors'])


def test_locked_period_and_real_rejected(env):
    batch = assert_preview(preview(env))
    with env.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.academic_periods SET is_locked=true WHERE id=:id'), {'id': batch['period_id']})
    assert commit(env, batch).json()['code'] == 'PERIOD_LOCKED'
    assert preview(env).json()['code'] == 'PERIOD_LOCKED'
    real = preview(env, period=env.context['periods']['real']['id'])
    assert real.status_code in (200, 201)


def test_csrf_and_import_roles(env):
    assert preview(env, csrf=False).status_code == 403
    batch = assert_preview(preview(env))
    assert commit(env, batch, csrf=False).status_code == 403
    for role in ['TUTOR', 'DIRECTOR', 'RESEARCHER']:
        login_as(env, role)
        assert preview(env).status_code == 403
        assert env.client.get(API + f"/imports/{batch['id']}").status_code == 403
        assert commit(env, batch).status_code == 403


def test_mid_commit_failure_rolls_back_every_academic_row_and_audit(env, monkeypatch):
    from app.services import imports
    batch = assert_preview(preview(env, [row(env), row(env, student_code=env.prefix + '-B')]))
    before = counts(env)
    original = imports.audit
    def invalid_audit(db, user, batch, request_id, action, **extra):
        db.add(AuditEvent(actor_id=uuid4(), entity_type='import_batch', entity_id=batch.id,
                         action=action, request_id=request_id, payload={'data_origin': 'REAL'}))
    monkeypatch.setattr(imports, 'audit', invalid_audit)
    failed = commit(env, batch)
    assert failed.status_code == 409 and failed.json()['code'] == 'INTEGRITY_CONFLICT'
    assert counts(env) == before
    assert env.client.get(API + f"/imports/{batch['id']}").json()['status'] == 'READY'
    monkeypatch.setattr(imports, 'audit', original)
    assert commit(env, batch).json()['created_snapshots'] == 2


@pytest.mark.parametrize('error,status', [(OperationalError,503), (IntegrityError,409), (ProgrammingError,500)])
def test_database_errors_are_sanitized_and_integrity_is_not_503(env, monkeypatch, error, status):
    from app.repositories import imports
    def fail(*args, **kwargs):
        raise error('private SQL text', {'password': 'private-value'}, Exception('internal host/path'))
    monkeypatch.setattr(imports, 'observed_records', fail)
    response = preview(env)
    assert response.status_code == status
    assert not any(value in response.text for value in ['private SQL', 'private-value', 'internal host'])
    sample('Error', response.json())


def test_private_file_tampering_is_not_committed(env):
    batch = assert_preview(preview(env))
    path = next(env.directory.glob('*.csv'))
    path.write_bytes(b'altered synthetic file')
    before = counts(env)
    response = commit(env, batch)
    assert response.status_code == 409 and response.json()['code'] == 'IMPORT_FILE_CHANGED'
    assert counts(env) == before


def test_predecessor_changed_with_same_planned_counts_is_stale(env):
    original = assert_preview(preview(env))
    assert commit(env, original).status_code == 200
    a = assert_preview(preview(env, [row(env, average_grade='15')]))
    b = assert_preview(preview(env, [row(env, average_grade='16')]))
    assert (a['planned_students'], a['planned_enrollments'], a['planned_snapshots']) == (0, 0, 1)
    assert commit(env, a).status_code == 200
    before = counts(env)
    denied = commit(env, b)
    assert denied.status_code == 409 and denied.json()['code'] == 'IMPORT_PREVIEW_STALE'
    assert counts(env) == before


def test_full_10000_rows_bom_and_bounded_locks(env):
    rows = [row(env, student_code=f'{env.prefix}-{i:05}') for i in range(10000)]
    batch = assert_preview(preview(env, content=b'\xef\xbb\xbf' + csv_bytes(rows)))
    assert batch['total_rows'] == batch['valid_rows'] == batch['planned_snapshots'] == 10000
    result = commit(env, batch)
    assert result.status_code == 200 and result.json()['created_snapshots'] == 10000
    assert env.client.get(API + '/students', params={'period_id': batch['period_id'], 'page': 100, 'page_size': 100}).json()['total'] == 10000


def test_detail_remains_consistent_during_concurrent_new_cut(env, monkeypatch):
    from app.repositories import students as repository
    first = assert_preview(preview(env))
    assert commit(env, first).status_code == 200
    second = assert_preview(preview(env, [row(env, cutoff_at='2026-06-01T12:00:00-05:00', target_date='2026-06-02', average_grade='18')]))
    student = env.client.get(API + '/students', params={'period_id': first['period_id']}).json()['items'][0]
    original = repository.public_student
    def insert_between_reads(db, enrollment_id):
        selected = original(db, enrollment_id)
        client = TestClient(env.app, cookies=env.client.cookies)
        try:
            assert commit(env, second, client=client).status_code == 200
        finally:
            client.close()
        return selected
    monkeypatch.setattr(repository, 'public_student', insert_between_reads)
    response = env.client.get(API + f"/students/{student['id']}", params={'period_id': first['period_id']})
    assert response.status_code == 200
    detail = response.json()
    assert detail['student']['latest_cutoff_at'] == detail['latest_snapshot']['cutoff_at']
    assert detail['student']['average_grade'] == detail['latest_snapshot']['average_grade'] == 14.25


def test_missing_or_changed_tutor_and_cross_year_section(env):
    with env.owner.begin() as conn:
        conn.execute(text("INSERT INTO risk_school.grade_sections(id,grade,code,school_year) VALUES (:id,3,'ONLY2027',2027)"), {'id': uuid4()})
    wrong_year = preview(env, [row(env, grade='3', section='ONLY2027')]).json()
    assert any(e['code'] == 'SECTION_NOT_FOUND' for e in wrong_year['errors'])
    batch = assert_preview(preview(env))
    with env.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.grade_sections SET tutor_id=null WHERE id=:id'), {'id': env.context['sections'][0]['id']})
    assert commit(env, batch).json()['code'] == 'IMPORT_PREVIEW_STALE'


def test_students_list_detail_timeline_permissions_and_pagination(env):
    own = row(env, student_code=env.prefix + '-A')
    other = row(env, student_code=env.prefix + '-B', grade='2')
    batch = assert_preview(preview(env, [own, other]))
    assert commit(env, batch).status_code == 200
    period = batch['period_id']
    listing = env.client.get(API + '/students', params={'period_id': period, 'page_size': 1}).json()
    sample('StudentPage', listing)
    assert listing['total'] == 2 and len(listing['items']) == 1
    first = listing['items'][0]
    assert first['anon_code'].endswith('-A') and first['risk_level'] is None
    assert first['evaluation_status'] == 'NOT_EVALUATED'
    assert first['average_grade'] == 14.25 and isinstance(first['average_grade'], float)
    second = env.client.get(API + '/students', params={'period_id': period, 'page': 2, 'page_size': 1}).json()['items'][0]
    assert first['id'] != second['id']
    for sort in ['anon_code','risk_desc','updated_desc']:
        response = env.client.get(API + '/students', params={'period_id': period, 'sort': sort})
        assert response.status_code == 200
        assert [s['id'] for s in response.json()['items']] == [first['id'], second['id']]
    assert env.client.get(API + '/students', params={'period_id': period, 'risk_level': 'LOW'}).json()['total'] == 0
    for search in ['%', "' OR 1=1 --", '_']:
        assert env.client.get(API + '/students', params={'period_id': period, 'search': search}).json()['total'] == 0
    assert env.client.get(API + '/students', params={'period_id': period, 'search': '-B'}).json()['total'] == 1
    for params in [{'page': 0}, {'page_size': 101}, {'sort': 'password_hash'}, {'search': 'x' * 41}, {'risk_level': 'NONE'}]:
        assert env.client.get(API + '/students', params={'period_id': period, **params}).status_code == 422
    detail = env.client.get(API + f"/students/{first['id']}", params={'period_id': period}).json()
    sample('StudentDetail', detail)
    assert detail['latest_prediction'] is None and detail['alerts'] == detail['interventions'] == []
    assert detail['latest_snapshot']['activities_pct'] is None
    assert set(detail['latest_snapshot']).isdisjoint({'import_batch_id', 'source_row_number', 'row_sha256'})
    timeline = env.client.get(API + f"/students/{first['id']}/timeline", params={'period_id': period}).json()
    sample('TimelineEventPage', timeline)
    assert timeline['total'] == 1 and timeline['items'][0]['event_type'] == 'SNAPSHOT'
    assert env.client.get(API + f"/students/{first['id']}/timeline", params={'period_id': period, 'page_size': 101}).status_code == 422
    assert env.client.get(API + f"/students/{first['id']}", params={'period_id': str(env.context['periods']['other_year']['id'])}).status_code == 404
    login_as(env, 'TUTOR')
    assert env.client.get(API + '/students', params={'period_id': period}).json()['total'] == 1
    for suffix in ['', '/timeline']:
        assert env.client.get(API + f"/students/{first['id']}" + suffix, params={'period_id': period}).status_code == 200
        # S5: UUID ajeno e inexistente comparten 404, sin revelar pertenencia.
        assert env.client.get(API + f"/students/{second['id']}" + suffix, params={'period_id': period}).status_code == 404
        assert env.client.get(API + f"/students/{uuid4()}" + suffix, params={'period_id': period}).status_code == 404
    assert env.client.get(API + '/students', params={'period_id': period, 'section_id': second['section_id']}).status_code == 403
    login_as(env, 'DIRECTOR')
    assert env.client.get(API + '/students', params={'period_id': period}).json()['total'] == 2
    login_as(env, 'RESEARCHER')
    for suffix in ['', f"/{first['id']}", f"/{first['id']}/timeline"]:
        assert env.client.get(API + '/students' + suffix, params={'period_id': period}).status_code == 403


def test_institutional_reads_and_processing_boundary(env, monkeypatch):
    real_period = env.context['periods']['real']['id']
    student_id, enrollment_id = uuid4(), uuid4()
    with env.owner.begin() as conn:
        conn.execute(text("INSERT INTO risk_school.students(id,anon_code,data_origin) VALUES (:id,:code,'REAL')"), {'id': student_id, 'code': env.prefix})
        conn.execute(text("INSERT INTO risk_school.enrollments(id,student_id,period_id,section_id,data_origin) VALUES (:id,:student,:period,:section,'REAL')"),
            {'id': enrollment_id, 'student': student_id, 'period': real_period, 'section': env.context['sections'][0]['id']})
    for suffix in ['', f'/{student_id}', f'/{student_id}/timeline']:
        response = env.client.get(API + '/students' + suffix, params={'period_id': str(real_period)})
        assert response.status_code == 200
    from app.services.processing_policy import require_processing_protocol
    monkeypatch.setattr('app.services.imports.require_processing_protocol', require_processing_protocol)
    response = preview(env)
    assert response.status_code == 422 and response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    assert not env.directory.exists()


def test_old_prediction_is_not_current_after_new_cut_and_timeline_keeps_history(env):
    # Fixture SQL sintética para probar lectura futura; no se entrena ni infiere ML.
    first = assert_preview(preview(env))
    assert commit(env, first).status_code == 200
    model_id, prediction_id = uuid4(), uuid4()
    with env.owner.begin() as conn:
        old = conn.execute(text('SELECT id,enrollment_id FROM risk_school.academic_snapshots WHERE import_batch_id=:id'), {'id': first['id']}).mappings().one()
        conn.execute(text("""INSERT INTO risk_school.model_versions(id,name,version,algorithm,data_origin,dataset_hash,
            artifact_sha256,artifact_key,feature_schema_version,reference_criterion_version,status,is_active,parameters,metrics,manifest)
            VALUES (:id,:name,'fixture','DUMMY','REAL',:hash,:hash,'fixture-only','demo-v1','fixture','APPROVED',false,'{}','{}','{}')"""),
            {'id': model_id, 'name': env.prefix, 'hash': '0' * 64})
        conn.execute(text("""INSERT INTO risk_school.predictions(id,enrollment_id,snapshot_id,model_id,data_origin,risk_level)
            VALUES (:id,:enrollment,:snapshot,:model,'REAL','HIGH')"""),
            {'id': prediction_id, 'enrollment': old['enrollment_id'], 'snapshot': old['id'], 'model': model_id})
    student = env.client.get(API + '/students', params={'period_id': first['period_id']}).json()['items'][0]
    assert student['evaluation_status'] == 'NOT_EVALUATED' and student['risk_level'] is None
    current = env.client.get(API + f"/students/{student['id']}", params={'period_id': first['period_id']}).json()
    sample('StudentDetail', current)
    assert current['latest_prediction'] is None
    new = assert_preview(preview(env, [row(env, cutoff_at='2026-05-03T12:00:00-05:00', target_date='2026-05-04')]))
    assert commit(env, new).status_code == 200
    detail = env.client.get(API + f"/students/{student['id']}", params={'period_id': first['period_id']}).json()
    assert detail['student']['evaluation_status'] == 'NOT_EVALUATED'
    assert detail['student']['risk_level'] is None and detail['latest_prediction'] is None
    events = env.client.get(API + f"/students/{student['id']}/timeline", params={'period_id': first['period_id'], 'page_size': 2}).json()
    assert events['total'] == 3 and len(events['items']) == 2
    second_page = env.client.get(API + f"/students/{student['id']}/timeline", params={'period_id': first['period_id'], 'page_size': 2, 'page': 2}).json()
    assert len(second_page['items']) == 1
    assert len({e['id'] for e in events['items'] + second_page['items']}) == 3
    with env.owner.begin() as conn:
        conn.execute(text('UPDATE risk_school.model_versions SET is_active=false WHERE id=:id'), {'id': model_id})


@pytest.mark.parametrize('same_batch', [True, False])
def test_concurrent_commits_lock_and_revalidate(env, monkeypatch, same_batch):
    from app.services import imports
    first = assert_preview(preview(env))
    second = first if same_batch else assert_preview(preview(env, [row(env, average_grade='18')]))
    held, release = threading.Event(), threading.Event()
    original = imports.insert_snapshots
    def hold_first(db, batch, rows, state):
        if str(batch.id) == first['id']:
            held.set()
            assert release.wait(10), 'Timed out waiting for the concurrency probe'
        return original(db, batch, rows, state)
    monkeypatch.setattr(imports, 'insert_snapshots', hold_first)
    clients = [TestClient(env.app, cookies=env.client.cookies) for _ in range(2)]
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(commit, env, first, client=clients[0])
            assert held.wait(10)
            b = executor.submit(commit, env, second, client=clients[1])
            blocked = False
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with env.owner.connect() as conn:
                        blocked = bool(conn.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND usename='riesgo_app' AND wait_event='advisory'")))
                    if blocked: break
                    time.sleep(0.025)
                assert blocked, 'Second real PostgreSQL connection did not wait on the lock'
            finally:
                release.set()
            assert a.result(timeout=10).status_code == 200
            result = b.result(timeout=10)
        if same_batch:
            assert result.status_code == 200 and result.json()['reused_result'] is True
        else:
            assert result.status_code == 409 and result.json()['code'] == 'IMPORT_PREVIEW_STALE'
            refreshed = assert_preview(preview(env, [row(env, average_grade='18')]))
            assert refreshed['preview_version'] == 2
            assert commit(env, refreshed).status_code == 200
    finally:
        release.set()
        for client in clients: client.close()
