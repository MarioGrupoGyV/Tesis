"""Upgrade S3 to S3.1 in a separate PostgreSQL database, retaining history.

The normal runner already exercises a clean upgrade to head. This second path
deliberately keeps historical DEMO/REAL fixtures without reassigning their origin.
"""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from test_s1_schema import assert_sqlstate

ROOT = Path(__file__).resolve().parents[2]


def fingerprints(connection):
    return {name: connection.scalar(text(
        f"SELECT md5(coalesce(string_agg(to_jsonb(t)::text,'|' ORDER BY id),'')) FROM risk_school.{name} t"))
        for name in ('app_users', 'academic_periods', 'students', 'audit_events')}


def test_upgrade_from_s3_preserves_accounts_audit_and_historical_origins(
        database_urls, synthetic_password_hash):
    # database_urls has already rejected non-test databases in conftest.
    owner_url = make_url(database_urls[1])
    database_name = 'riesgo_escolar_test_s31_upgrade_' + uuid4().hex[:12]
    bootstrap = create_engine(owner_url, isolation_level='AUTOCOMMIT', hide_parameters=True)
    try:
        with bootstrap.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE {database_name} OWNER riesgo_owner')
            connection.exec_driver_sql(f'REVOKE ALL ON DATABASE {database_name} FROM PUBLIC')
            connection.exec_driver_sql(f'GRANT CONNECT ON DATABASE {database_name} TO riesgo_app')
    finally:
        bootstrap.dispose()
    migrated_url = owner_url.set(database=database_name)
    environment = os.environ.copy()
    environment.pop('MIGRATION_DATABASE_URL_FILE', None)
    environment['MIGRATION_DATABASE_URL'] = migrated_url.render_as_string(hide_password=False)

    def migrate(revision):
        # Credentials stay in the child environment and never appear in argv.
        result = subprocess.run([sys.executable, '-m', 'alembic', '-c',
            'backend/alembic.ini', 'upgrade', revision], cwd=ROOT, env=environment,
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f'Isolated Alembic upgrade to {revision} failed'

    migrate('0001_demo_schema')
    engine = create_engine(migrated_url, hide_parameters=True)
    actor_id, historical_model_id, institutional_model_id = uuid4(), uuid4(), uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO risk_school.app_users(id,email,display_name,password_hash,role) VALUES(:id,:email,'Fixture de migración S3.1',:hash,'ADMIN')"),
                {'id': actor_id, 'email': 'migration-' + uuid4().hex + '@example.com', 'hash': synthetic_password_hash})
            for origin in ('DEMO', 'REAL'):
                period_id, student_id = uuid4(), uuid4()
                connection.execute(text("INSERT INTO risk_school.academic_periods(id,code,school_year,start_date,end_date,data_origin) VALUES(:id,:code,2025,'2025-01-01','2025-12-31',:origin)"),
                    {'id': period_id, 'code': 'historical-' + uuid4().hex[:12], 'origin': origin})
                connection.execute(text("INSERT INTO risk_school.students(id,anon_code,data_origin) VALUES(:id,:code,:origin)"),
                    {'id': student_id, 'code': 'historical-' + uuid4().hex[:12], 'origin': origin})
                model_id = historical_model_id if origin == 'DEMO' else institutional_model_id
                connection.execute(text("""INSERT INTO risk_school.model_versions(id,name,version,algorithm,data_origin,dataset_hash,
                    artifact_sha256,artifact_key,feature_schema_version,reference_criterion_version,status,is_active,parameters,metrics,manifest,created_by)
                    VALUES(:id,:name,'historical-fixture','DUMMY',:origin,repeat('0',64),repeat('0',64),'historical-fixture',
                    'demo-v1','fixture','APPROVED',:active,'{}','{}','{}',:actor)"""),
                    {'id': model_id, 'name': 'historical-' + uuid4().hex, 'origin': origin,
                     'active': origin == 'DEMO', 'actor': actor_id})
            connection.execute(text("INSERT INTO risk_school.audit_events(actor_id,entity_type,action,request_id,payload) VALUES(:actor,'MIGRATION_FIXTURE','HISTORICAL_EVIDENCE',:request,'{\"scope\":\"ISOLATED_TEST\"}')"),
                {'actor': actor_id, 'request': uuid4()})
        migrate('0002_institutional_boundary')
        with engine.connect() as connection:
            before = fingerprints(connection)
            historical_model = connection.execute(text('SELECT id,data_origin,is_active,manifest FROM risk_school.model_versions ORDER BY id')).mappings().all()
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0002_institutional_boundary'
        migrate('0003_synthetic_study')
        with engine.begin() as connection:
            assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0003_synthetic_study'
            assert len(inspect(connection).get_table_names(schema='risk_school')) == 14
            assert fingerprints(connection) == before
            assert connection.execute(text('SELECT id,data_origin,is_active,manifest FROM risk_school.model_versions ORDER BY id')).mappings().all() == historical_model
            assert connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='processing_origin'")) == 9
            assert connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname IN ('institutional_origin','model_activation_pending','demo_only_active_model')")) == 0
            assert_sqlstate(connection, "UPDATE risk_school.model_versions SET is_active=true WHERE id=:id", {'id': institutional_model_id}, '23514')
            assert_sqlstate(connection, "INSERT INTO risk_school.academic_periods(code,school_year,start_date,end_date,data_origin) VALUES(:code,2025,'2025-01-01','2025-12-31','DEMO')", {'code': uuid4().hex}, '23514')
            connection.execute(text("INSERT INTO risk_school.academic_periods(code,school_year,start_date,end_date,data_origin) VALUES(:code,2025,'2025-01-01','2025-12-31','SYNTHETIC')"), {'code': uuid4().hex})
            assert connection.scalar(text("SELECT has_table_privilege('riesgo_app','risk_school.synthetic_studies','INSERT')"))
            assert not connection.scalar(text("SELECT has_table_privilege('riesgo_app','risk_school.synthetic_studies','DELETE')"))
    finally:
        engine.dispose()
    # Retain the isolated database as test evidence; never delete operational or
    # historical volumes/databases as part of a migration test.
