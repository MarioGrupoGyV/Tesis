"""Comprueba HTTP real y persistencia S1. Nunca imprime secretos ni elimina el volumen."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
SECRET_DIR = Path(os.environ.get('S1_SECRETS_DIR', ROOT / '.local/secrets'))
BASE = os.environ.get('S1_BASE_URL', 'http://127.0.0.1:15173').rstrip('/')
PREFIX = '/api/v1'


def fingerprint():
    url = make_url((SECRET_DIR / 'owner-database-url').read_text().strip())
    url = url.set(host='127.0.0.1', port=int(os.environ.get('DB_PORT', '55432')))
    engine = create_engine(url, hide_parameters=True, connect_args={'connect_timeout': 5})
    try:
        with engine.connect() as connection:
            tables = connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='risk_school' ORDER BY tablename")).all()
            assert len(tables) == 13, 'Se esperaban trece tablas de la demo'
            result = {}
            for table in tables:
                # Los nombres proceden del catálogo y son identificadores del diseño revisado.
                quoted = connection.dialect.identifier_preparer.quote(table)
                rows = connection.scalars(text(f'SELECT to_jsonb(t)::text FROM risk_school.{quoted} t ORDER BY id')).all()
                result[table] = {'rows': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
            return result
    finally:
        engine.dispose()


def compose(*arguments):
    subprocess.run(['docker', 'compose', *arguments], cwd=ROOT, check=True)


def main():
    credentials = json.loads((SECRET_DIR / 'demo-credentials.json').read_text())
    report = {'status': 'COMPROBADO', 'data_origin': 'DEMO', 'base_url': BASE,
              'scope': 'S1: health, sesiones, catalogos y persistencia', 'roles': {}}
    clients = []
    try:
        for key, role in [('admin', 'ADMIN'), ('tutor', 'TUTOR'), ('director', 'DIRECTOR')]:
            client = httpx.Client(base_url=BASE, timeout=15, trust_env=False)
            clients.append(client)
            for endpoint in ['health/live', 'health/ready']:
                response = client.get(f'{PREFIX}/{endpoint}')
                assert response.status_code == 200, f'{endpoint} no disponible'
                assert response.json()['status'] == 'ok'
            response = client.post(f'{PREFIX}/auth/login', json=credentials[key], headers={'Origin': BASE})
            assert response.status_code == 200, f'Login {role} falló'
            assert response.json()['user']['role'] == role
            cookie = response.headers['set-cookie'].lower()
            assert 'httponly' in cookie and 'samesite=lax' in cookie
            assert 'path=/' in cookie and 'max-age=28800' in cookie
            assert client.get(f'{PREFIX}/auth/me').json()['role'] == role
            csrf = client.get(f'{PREFIX}/auth/csrf')
            assert csrf.status_code == 200 and len(csrf.json()['csrf_token']) == 64
            periods = client.get(f'{PREFIX}/periods').json()
            assert len(periods) == 1 and periods[0]['data_origin'] == 'DEMO'
            sections = client.get(f'{PREFIX}/sections', params={'period_id': periods[0]['id']}).json()
            expected_count = 1 if role == 'TUTOR' else 2
            assert len(sections) == expected_count, f'Alcance incorrecto para {role}'
            denied = client.post(f'{PREFIX}/auth/logout')
            assert denied.status_code == 403 and denied.json()['code'] == 'CSRF_INVALID'
            report['roles'][role] = {'login': 200, 'me': 200, 'csrf': 200, 'periods': len(periods),
                                     'sections': len(sections), 'logout_without_csrf': 403}
        before = fingerprint()
        assert before['app_users']['rows'] == 3 and before['academic_periods']['rows'] == 1
        assert before['grade_sections']['rows'] == 2 and before['students']['rows'] == 0
        compose('down')  # No -v: conservar el volumen y las trece tablas.
        compose('up', '-d', '--wait', 'db', 'api', 'web')
        after = fingerprint()
        assert after == before, 'Cambió el contenido persistido durante el reinicio'
        report['restart'] = {'method': 'compose down / up --wait (sin -v ni semilla)',
                             'all_13_tables_identical': True, 'before': before, 'after': after}
        for client, role in zip(clients, ['ADMIN', 'TUTOR', 'DIRECTOR'], strict=True):
            response = client.get(f'{PREFIX}/auth/me')
            assert response.status_code == 200 and response.json()['role'] == role
            csrf = client.get(f'{PREFIX}/auth/csrf').json()['csrf_token']
            replay = httpx.Client(base_url=BASE, timeout=15, trust_env=False, cookies=client.cookies)
            try:
                assert client.post(f'{PREFIX}/auth/logout', headers={'Origin': BASE, 'X-CSRF-Token': csrf}).status_code == 204
                assert replay.get(f'{PREFIX}/auth/me').status_code == 401
            finally:
                replay.close()
            report['roles'][role].update({'session_after_restart': 200, 'logout': 204, 'revoked_cookie': 401})
        path = ROOT / 'tests/evidence/s1-runtime.json'
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print('COMPROBADO: salud, tres roles, CSRF, revocacion y trece tablas conservadas; evidencia tests/evidence/s1-runtime.json')
    finally:
        for client in clients:
            client.close()


if __name__ == '__main__':
    main()
