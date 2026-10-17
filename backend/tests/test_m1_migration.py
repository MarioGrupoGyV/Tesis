"""0004→0005 conserva todas las columnas anteriores y privilegios riesgo_app."""
import os
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url
from conftest import create_context
from test_s1_schema import assert_sqlstate


def test_m1_upgrade_preserves_old_columns_and_grants(database_urls,synthetic_password,synthetic_password_hash):
    owner=make_url(database_urls[1])
    name='riesgo_escolar_test_m1_upgrade_'+uuid4().hex[:12]
    engine=create_engine(owner,isolation_level='AUTOCOMMIT',hide_parameters=True)
    with engine.connect() as db:
        db.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        db.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        db.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    engine.dispose()
    environment={**os.environ,'MIGRATION_DATABASE_URL':owner.set(database=name).render_as_string(hide_password=False)}
    environment.pop('MIGRATION_DATABASE_URL_FILE',None)
    def migrate(rev):
        result=subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade',rev],env=environment,capture_output=True)
        assert result.returncode==0,'Isolated upgrade failed'
    migrate('0004_followup')
    engine=create_engine(make_url(database_urls[0]).set(database=name),hide_parameters=True)
    with engine.begin() as db:
        context=create_context(db,synthetic_password,synthetic_password_hash)
        student=uuid4(); enrollment=uuid4(); batch=uuid4(); snapshot=uuid4()
        p=context['periods']['real']['id']; g=context['sections'][0]['id']; actor=context['accounts']['ADMIN']['id']
        db.execute(text("INSERT INTO risk_school.students(id,anon_code,data_origin) VALUES(:id,:code,'REAL')"),{'id':student,'code':'M1-LEGACY-'+uuid4().hex[:10]})
        db.execute(text("INSERT INTO risk_school.enrollments(id,student_id,period_id,section_id,data_origin) VALUES(:id,:s,:p,:g,'REAL')"),{'id':enrollment,'s':student,'p':p,'g':g})
        db.execute(text("INSERT INTO risk_school.import_batches(id,period_id,data_origin,created_by,file_name,file_sha256,storage_key) VALUES(:id,:p,'REAL',:a,'fixture.csv',repeat('a',64),'fixture.csv')"),{'id':batch,'p':p,'a':actor})
        db.execute(text("""INSERT INTO risk_school.academic_snapshots(id,enrollment_id,period_id,data_origin,import_batch_id,
          window_start,cutoff_at,available_at,target_date,average_grade,missing_fraction,source_row_number,row_sha256)
          VALUES(:id,:e,:p,'REAL',:b,'2026-01-01','2026-05-01T17:00:00Z','2026-05-01T16:00:00Z','2026-05-02',0,0.8,2,repeat('b',64))"""),{'id':snapshot,'e':enrollment,'p':p,'b':batch})
        db.execute(text("INSERT INTO risk_school.audit_events(actor_id,entity_type,entity_id,action,request_id) VALUES(:a,'SNAPSHOT',:id,'M1_UPGRADE_FIXTURE',:r)"),{'a':actor,'id':snapshot,'r':uuid4()})
    with engine.connect() as db:
        inspector=inspect(db)
        columns={t:[c['name'] for c in inspector.get_columns(t,schema='risk_school')] for t in inspector.get_table_names(schema='risk_school')}
        def digest(table):
            fields=','.join(columns[table])
            return db.scalar(text(f"SELECT md5(coalesce(string_agg(to_jsonb(x)::text,'|' ORDER BY id),'')) FROM (SELECT {fields} FROM risk_school.{table}) x"))
        before={t:digest(t) for t in columns}
    migrate('head')
    with engine.connect() as db:
        assert {t:digest(t) for t in columns}==before
        assert db.scalar(text('SELECT full_name FROM risk_school.students WHERE id=:id'),{'id':student}) is None
        assert db.execute(text('SELECT entry_channel,target_date FROM risk_school.academic_snapshots WHERE id=:id'),{'id':snapshot}).one()[0]=='CSV'
        assert not db.scalar(text("SELECT has_schema_privilege(current_user,'risk_school','CREATE')"))
        for table in columns:
            for privilege in ('DELETE','TRUNCATE'):
                assert not db.scalar(text('SELECT has_table_privilege(current_user,:table,:privilege)'),{'table':'risk_school.'+table,'privilege':privilege})
        assert_sqlstate(db,'UPDATE risk_school.academic_snapshots SET average_grade=1 WHERE id=:id',{'id':snapshot},'42501')
    engine.dispose()
