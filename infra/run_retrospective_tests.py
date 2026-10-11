"""Final targeted checks against a new isolated PostgreSQL, after full regression."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

urls = {role: make_url(Path(f'/run/secrets/{role}_url').read_text().strip()).set(
    host='dbtest', port=5432, database='riesgo_escolar_test').render_as_string(hide_password=False)
    for role in ('owner', 'app')}
bootstrap = create_engine(urls['owner'], isolation_level='AUTOCOMMIT', hide_parameters=True)
database = 'riesgo_escolar_test_retro_' + uuid4().hex[:12]
with bootstrap.connect() as conn:
    conn.exec_driver_sql(f'CREATE DATABASE {database} OWNER riesgo_owner')
    conn.exec_driver_sql(f'REVOKE ALL ON DATABASE {database} FROM PUBLIC')
    conn.exec_driver_sql(f'GRANT CONNECT ON DATABASE {database} TO riesgo_app')
bootstrap.dispose()
urls = {role: make_url(url).set(database=database).render_as_string(hide_password=False) for role, url in urls.items()}
os.environ.update(TEST_DATABASE_URL=urls['app'], ADMIN_DATABASE_URL=urls['owner'], DATABASE_URL=urls['app'],
    MIGRATION_DATABASE_URL=urls['owner'], APP_ENV='test', CSRF_SECRET='isolated-retro-tests-CSRF-key-at-least-32-bytes')
subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'], check=True)
result = subprocess.run([sys.executable, '-m', 'pytest', 'backend/tests/test_retrospective.py', '-q', '--tb=short',
    '-o', 'cache_dir=/tmp/pytest-cache', '--junitxml=/evidence/retro-final-tests.xml'])
Path('/evidence/retro-final-tests-environment.json').write_text(json.dumps({
    'status': 'COMPROBADO' if result.returncode == 0 else 'FALLIDO', 'database': database,
    'final_application_sources_mounted_readonly': True, 'exit_code': result.returncode}, indent=2))
raise SystemExit(result.returncode)
