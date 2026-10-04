"""Pruebas en Linux/Python fijado, contra PostgreSQL aislado sin puertos del host."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
assert sys.version_info[:3] == (3, 12, 12) and platform.system() == 'Linux'
assert os.environ.get('TEST_REPORT_NAME', 's2-pytest-linux').replace('-', '').isalnum()
report = os.environ.get('TEST_REPORT_NAME', 's2-pytest-linux')
urls = {role: make_url(Path(f'/run/secrets/{role}_url').read_text().strip()).set(
    host='dbtest', port=5432, database='riesgo_escolar_demo_s2_test'
).render_as_string(hide_password=False) for role in ('owner', 'app')}
os.environ.update(TEST_DATABASE_URL=urls['app'], ADMIN_DATABASE_URL=urls['owner'],
                  DATABASE_URL=urls['app'], MIGRATION_DATABASE_URL=urls['owner'],
                  APP_ENV='test', DATA_ORIGIN='DEMO', REAL_MODE_ENABLED='false',
                  CSRF_SECRET='isolated-linux-tests-CSRF-key-at-least-32-bytes')
# Cada ejecución empieza sin tablas ni registros; las bases anteriores se conservan.
bootstrap = create_engine(urls['owner'], isolation_level='AUTOCOMMIT', hide_parameters=True)
database_name = 'riesgo_escolar_demo_s2_test_' + uuid4().hex[:12]
with bootstrap.connect() as conn:
    conn.exec_driver_sql(f'CREATE DATABASE {database_name} OWNER riesgo_owner')
    conn.exec_driver_sql(f'REVOKE ALL ON DATABASE {database_name} FROM PUBLIC')
    conn.exec_driver_sql(f'GRANT CONNECT ON DATABASE {database_name} TO riesgo_app')
bootstrap.dispose()
urls = {role: make_url(url).set(database=database_name).render_as_string(hide_password=False)
        for role, url in urls.items()}
os.environ.update(TEST_DATABASE_URL=urls['app'], ADMIN_DATABASE_URL=urls['owner'],
                  DATABASE_URL=urls['app'], MIGRATION_DATABASE_URL=urls['owner'])
subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
               cwd=ROOT, check=True)
engine = create_engine(urls['owner'], hide_parameters=True, connect_args={'connect_timeout': 5})
with engine.connect() as conn:
    version = conn.scalar(text('SHOW server_version'))
engine.dispose()
result = subprocess.run([sys.executable, '-m', 'pytest', 'backend/tests', '-q', '--tb=short',
                         '-o', 'cache_dir=/tmp/pytest-cache',
                         f'--junitxml=/evidence/{report}.xml'], cwd=ROOT)
Path(f'/evidence/{report}-environment.json').write_text(json.dumps({
    'status': 'COMPROBADO' if result.returncode == 0 else 'FALLIDO',
    'python': platform.python_version(), 'platform': platform.system(), 'postgresql': version,
    'database': database_name, 'exit_code': result.returncode,
    'isolated_compose': 'riesgo-escolar-s2-tests',
}, indent=2) + '\n')
sys.exit(result.returncode)
