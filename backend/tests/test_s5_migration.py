"""Upgrade 0003→S5 en una DB separada; propietario solo para migraciones."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from conftest import create_context
from test_s1_schema import assert_sqlstate

ROOT=Path(__file__).resolve().parents[2]


def test_clean_head_privileges_immutable_decisions_and_upgrade_s4_preserves_history(
        database_urls,synthetic_password,synthetic_password_hash):
    owner=make_url(database_urls[1])
    name='riesgo_escolar_test_s5_upgrade_'+uuid4().hex[:12]
    with create_engine(owner,isolation_level='AUTOCOMMIT',hide_parameters=True).connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        connection.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        connection.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    owner=owner.set(database=name)
    application=make_url(database_urls[0]).set(database=name)
    environment={**os.environ,'MIGRATION_DATABASE_URL':owner.render_as_string(hide_password=False)}
    environment.pop('MIGRATION_DATABASE_URL_FILE',None)
    def migrate(revision):
        result=subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade',revision],
            cwd=ROOT,env=environment,capture_output=True,text=True,timeout=60)
        assert result.returncode==0,f'La migración aislada a {revision} falló'
    migrate('0003_synthetic_study')
    engine=create_engine(application,hide_parameters=True)
    try:
        with engine.begin() as db:
            assert db.scalar(text('SELECT current_user'))=='riesgo_app'
            context=create_context(db,synthetic_password,synthetic_password_hash)
            db.execute(text("INSERT INTO risk_school.audit_events(actor_id,entity_type,action,request_id,payload) VALUES(:actor,'S5_MIGRATION_FIXTURE','S4_EVIDENCE',:request,'{\"scope\":\"ISOLATED_TEST\"}')"),
                {'actor':context['accounts']['ADMIN']['id'],'request':uuid4()})
        with engine.connect() as db:
            tables=inspect(db).get_table_names(schema='risk_school'); assert len(tables)==14
            before={table:db.scalar(text(f"SELECT md5(coalesce(string_agg(to_jsonb(x)::text,'|' ORDER BY id),'')) FROM risk_school.{table} x")) for table in tables}
        migrate('head')
        with engine.connect() as db:
            assert len(inspect(db).get_table_names(schema='risk_school'))==15
            assert {table:db.scalar(text(f"SELECT md5(coalesce(string_agg(to_jsonb(x)::text,'|' ORDER BY id),'')) FROM risk_school.{table} x")) for table in tables}==before
            assert db.scalar(text('SELECT count(*) FROM risk_school.followup_decisions'))==0
            fields={column['name'] for column in inspect(db).get_columns('interventions',schema='risk_school')}
            assert {'creation_key','creation_payload_sha256'}<=fields
            assert db.scalar(text("SELECT has_table_privilege(current_user,'risk_school.followup_decisions','INSERT')"))
            for table in ('followup_decisions','alerts','interventions'):
                assert not db.scalar(text('SELECT has_table_privilege(current_user,:table,\'DELETE\')'),{'table':'risk_school.'+table})
            for privilege in ('UPDATE','TRUNCATE'):
                assert not db.scalar(text('SELECT has_table_privilege(current_user,:table,:privilege)'),{'table':'risk_school.followup_decisions','privilege':privilege})
            fks=inspect(db).get_foreign_keys('followup_decisions',schema='risk_school')
            assert any('prediction_id' in fk['constrained_columns'] and 'data_origin' in fk['constrained_columns'] for fk in fks)
            assert any('alert_id' in fk['constrained_columns'] and 'enrollment_id' in fk['constrained_columns'] for fk in fks)
            assert_sqlstate(db,'UPDATE risk_school.followup_decisions SET decision=decision WHERE false',{},'42501')
            assert_sqlstate(db,'DELETE FROM risk_school.alerts WHERE false',{},'42501')
    finally:
        engine.dispose()
