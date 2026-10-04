"""Recorrido HTTP S2 reproducible con muestras DEMO; conserva DB y volumen privado."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from smoke_s1 import fingerprint

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('S1_BASE_URL', 'http://127.0.0.1:15173').rstrip('/')
API = '/api/v1'
SAMPLES = ROOT / 'tests/fixtures/synthetic'


def compose(*args, capture=False):
    if capture:
        return subprocess.check_output(['docker', 'compose', *args], cwd=ROOT, text=True, encoding='utf-8').strip()
    subprocess.run(['docker', 'compose', *args], cwd=ROOT, check=True)


def private_files():
    # Solo devolver cantidad y hash agregado: no filas CSV ni rutas privadas.
    code = "import hashlib,json; from pathlib import Path; p=Path('/var/lib/riesgo/imports'); f=sorted((x.name,hashlib.sha256(x.read_bytes()).hexdigest()) for x in p.glob('*.csv')); print(json.dumps({'files':len(f),'sha256':hashlib.sha256(json.dumps(f).encode()).hexdigest()}))"
    return json.loads(compose('exec', '-T', 'api', 'python', '-c', code, capture=True))


def main():
    credentials = json.loads((ROOT / '.local/secrets/demo-credentials.json').read_text())
    app_url = make_url((ROOT / '.local/secrets/app-database-url').read_text().strip()).set(
        host='127.0.0.1', port=int(os.environ.get('DB_PORT', '55432')))
    engine = create_engine(app_url, hide_parameters=True, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT current_user')) == 'riesgo_app'
    engine.dispose()
    report = {'status': 'COMPROBADO', 'data_origin': 'DEMO', 'database_role': 'riesgo_app', 'operations': []}
    with httpx.Client(base_url=BASE, timeout=30, trust_env=False) as client:
        response = client.post(API + '/auth/login', json=credentials['admin'], headers={'Origin': BASE})
        assert response.status_code == 200, 'Login admin fallido'
        csrf = {'X-CSRF-Token': response.json()['csrf_token']}
        period = client.get(API + '/periods').json()[0]['id']

        def upload(name):
            result = client.post(API + '/imports/preview', data={'period_id': period}, headers=csrf,
                                 files={'file': (name, (SAMPLES / name).read_bytes(), 'text/csv')})
            assert result.status_code in (200, 201), 'Vista previa fallida'
            batch = result.json()
            report['operations'].append({'sample': name, 'batch_id': batch['id'], 'status': batch['status'],
                                          'rows': batch['total_rows'], 'invalid': batch['invalid_rows']})
            return batch

        invalid = upload('invalid.csv')
        assert invalid['status'] == 'FAILED'
        denied = client.post(API + f"/imports/{invalid['id']}/commit", headers=csrf,
                             json={'expected_preview_version': invalid['preview_version']})
        assert denied.status_code == 422
        valid = upload('valid.csv')
        body = {'expected_preview_version': valid['preview_version']}
        assert client.post(API + f"/imports/{valid['id']}/commit", json=body).status_code == 403
        committed = client.post(API + f"/imports/{valid['id']}/commit", json=body, headers=csrf)
        assert committed.status_code == 200 and committed.json()['created_snapshots'] == 2
        repeated = client.post(API + f"/imports/{valid['id']}/commit", json=body, headers=csrf)
        assert repeated.json()['reused_result'] is True
        corrected = upload('correction.csv')
        assert client.post(API + f"/imports/{corrected['id']}/commit", headers=csrf,
                           json={'expected_preview_version': corrected['preview_version']}).status_code == 200
        listing = client.get(API + '/students', params={'period_id': period, 'search': 'DEMO-S2-00'}).json()
        assert listing['total'] == 2
        own, other = listing['items']
        assert all(item['evaluation_status'] == 'NOT_EVALUATED' and item['risk_level'] is None for item in listing['items'])
        detail = client.get(API + f"/students/{own['id']}", params={'period_id': period}).json()
        assert detail['latest_snapshot']['revision'] == 2 and detail['latest_snapshot']['average_grade'] == 16
        assert client.get(API + f"/students/{own['id']}/timeline", params={'period_id': period}).json()['total'] == 2
        assert client.get(API + f"/imports/{corrected['id']}").json()['status'] == 'COMMITTED'
        for role in ('tutor', 'director'):
            with httpx.Client(base_url=BASE, timeout=15, trust_env=False) as scoped:
                login = scoped.post(API + '/auth/login', json=credentials[role], headers={'Origin': BASE})
                assert login.status_code == 200
                filtered = scoped.get(API + '/students', params={'period_id': period, 'search': 'DEMO-S2-00'})
                assert filtered.json()['total'] == (1 if role == 'tutor' else 2)
                if role == 'tutor':
                    assert scoped.get(API + f"/students/{other['id']}/timeline", params={'period_id': period}).status_code == 403
                assert scoped.get(API + f"/imports/{valid['id']}").status_code == 403
                assert scoped.post(API + '/auth/logout', headers={'X-CSRF-Token': login.json()['csrf_token']}).status_code == 204
        before, files_before = fingerprint(), private_files()
        compose('down')  # Sin -v, sin semilla: ambos volúmenes se conservan.
        compose('up', '-d', '--wait')
        after, files_after = fingerprint(), private_files()
        assert before == after and files_before == files_after
        assert client.get(API + '/auth/me').status_code == 200
        assert client.get(API + f"/imports/{valid['id']}").json()['status'] == 'COMMITTED'
        assert client.post(API + '/auth/logout', headers=csrf).status_code == 204
        report.update(all_13_tables_unchanged=True, private_files_unchanged=True,
                      private_volume=files_after, academic_counts={k: after[k]['rows'] for k in
                      ['students', 'enrollments', 'academic_snapshots', 'import_batches']},
                      repeated_commit=True, csrf_missing_status=403, invalid_commit_status=422,
                      own_other_scope=True, session_survives_restart=True)
    (ROOT / 'tests/evidence/s2-runtime.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('COMPROBADO S2 HTTP: importacion, revision, consultas, permisos y persistencia de DB/archivos privados.')


if __name__ == '__main__':
    main()
