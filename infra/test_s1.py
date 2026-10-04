"""Prepara y prueba una DB PostgreSQL aislada, sin borrar ni tocar la demo operativa."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = 'riesgo_escolar_demo_s1_test'


def urls():
    secrets_dir = ROOT / '.local/secrets'
    owner = make_url((secrets_dir / 'owner-database-url').read_text().strip())
    app = make_url((secrets_dir / 'app-database-url').read_text().strip())
    port = int(os.environ.get('DB_PORT', '55432'))
    return (owner.set(host='127.0.0.1', port=port), app.set(host='127.0.0.1', port=port))


def test_environment():
    owner, app = urls()
    return {**os.environ,
            'TEST_DATABASE_URL': app.set(database=TEST_DB).render_as_string(hide_password=False),
            'ADMIN_DATABASE_URL': owner.set(database=TEST_DB).render_as_string(hide_password=False),
            'DATABASE_URL': app.set(database=TEST_DB).render_as_string(hide_password=False),
            'APP_ENV': 'test', 'REAL_MODE_ENABLED': 'false', 'DATA_ORIGIN': 'DEMO',
            'CSRF_SECRET': 'test-only-CSRF-key-32-characters-minimum'}


def prepare_db():
    owner, _ = urls()
    engine = create_engine(owner, isolation_level='AUTOCOMMIT', hide_parameters=True,
                           connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        exists = conn.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': TEST_DB})
        if not exists:
            conn.exec_driver_sql(f'CREATE DATABASE {TEST_DB} OWNER riesgo_owner')
            conn.exec_driver_sql(f'REVOKE ALL ON DATABASE {TEST_DB} FROM PUBLIC')
            conn.exec_driver_sql(f'GRANT CONNECT ON DATABASE {TEST_DB} TO riesgo_app')
    engine.dispose()
    test_engine = create_engine(owner.set(database=TEST_DB), hide_parameters=True,
                                connect_args={'connect_timeout': 5})
    with test_engine.connect() as conn:
        before = conn.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='risk_school'"))
    test_engine.dispose()
    env = test_environment()
    env['MIGRATION_DATABASE_URL'] = env['ADMIN_DATABASE_URL']
    env.pop('MIGRATION_DATABASE_URL_FILE', None)
    subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
                   cwd=ROOT, env=env, check=True)
    with create_engine(owner.set(database=TEST_DB), hide_parameters=True,
                       connect_args={'connect_timeout': 5}).connect() as conn:
        after = conn.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='risk_school'"))
        revision = conn.scalar(text('SELECT version_num FROM public.alembic_version'))
        version = conn.scalar(text('SHOW server_version'))
    assert after == 13 and revision == '0001_demo_schema'
    result = {'status': 'COMPROBADO', 'database': TEST_DB, 'fresh_created': not bool(exists),
              'tables_before': before, 'tables_after': after, 'revision': revision,
              'postgresql_version': version, 'synthetic_only': True, 'deleted_data': False}
    (ROOT / 'tests/evidence/s1-database.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


def run_tests():
    env = test_environment()
    subprocess.run([sys.executable, '-m', 'pytest', 'backend/tests', '-q', '--tb=short',
                    '--junitxml=tests/evidence/s1-pytest.xml'], cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare-db', 'pytest'])
    command = parser.parse_args().command
    prepare_db() if command == 'prepare-db' else run_tests()
