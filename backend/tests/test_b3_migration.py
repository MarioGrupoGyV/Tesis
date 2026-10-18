"""0006→0007: aditiva, conserva columnas anteriores, privilegios de riesgo_app y relojes retrospectivos."""
import os
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from conftest import create_context
from test_s1_schema import assert_sqlstate


def new_database(database_urls, label):
    owner = make_url(database_urls[1])
    name = f'riesgo_escolar_test_{label}_' + uuid4().hex[:12]
    engine = create_engine(owner, isolation_level='AUTOCOMMIT', hide_parameters=True)
    with engine.connect() as db:
        db.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        db.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        db.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    engine.dispose()
    environment = {**os.environ, 'MIGRATION_DATABASE_URL': owner.set(database=name).render_as_string(hide_password=False)}
    environment.pop('MIGRATION_DATABASE_URL_FILE', None)

    def migrate(revision):
        result = subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', revision],
                                env=environment, capture_output=True)
        assert result.returncode == 0, 'Isolated upgrade failed to ' + revision
    return name, migrate


def check_structure(engine):
    with engine.connect() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version')) == '0007_real_protocol'
        inspector = inspect(db)
        tables = set(inspector.get_table_names(schema='risk_school'))
        assert {'processing_protocols', 'risk_references'} <= tables
        protocol = {c['name'] for c in inspector.get_columns('processing_protocols', schema='risk_school')}
        # Sin consentimientos, documentos, autorizadores ni fechas de permiso.
        assert not {name for name in protocol if any(word in name for word in ('consent', 'assent', 'document', 'authorizer', 'permit'))}
        assert {'authorization_confirmed_by_admin', 'confirmed_by', 'confirmed_at', 'risk_rule', 'opportune_windows'} <= protocol
        studies = {c['name'] for c in inspector.get_columns('synthetic_studies', schema='risk_school')}
        assert {'kind', 'protocol_id'} <= studies
        assert 'as_of_at' in {c['name'] for c in inspector.get_columns('predictions', schema='risk_school')}
        assert 'detected_at' in {c['name'] for c in inspector.get_columns('alerts', schema='risk_school')}
        for table, allowed in (('processing_protocols', {'SELECT', 'INSERT', 'UPDATE'}), ('risk_references', {'SELECT', 'INSERT'})):
            for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                granted = db.scalar(text('SELECT has_table_privilege(:role,:table,:privilege)'),
                                    {'role': 'riesgo_app', 'table': 'risk_school.' + table, 'privilege': privilege})
                assert granted == (privilege in allowed), (table, privilege)
        for function in ('protect_confirmed_protocol()', 'check_risk_reference()', 'real_protocol_covers_period(uuid)',
                         'real_student_eligible(uuid)', 'check_real_student_eligibility()', 'set_retrospective_defaults()'):
            assert db.scalar(text('SELECT has_function_privilege(:r,:f,\'EXECUTE\')'), {'r': 'riesgo_app', 'f': 'risk_school.' + function})
            assert not db.scalar(text('SELECT has_function_privilege(\'public\',:f,\'EXECUTE\')'), {'f': 'risk_school.' + function})
        # El trigger de elegibilidad NO está asociado todavía: el comportamiento vigente no cambia en 3B-1.
        assert db.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgfoid='risk_school.check_real_student_eligibility()'::regprocedure")) == 0
        assert db.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='students_eligibility_check'")) == 1
        # Los CHECK de origen de modelos, lotes y estudios no se amplían.
        assert db.scalar(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='model_versions_synthetic_provenance'")).count('SYNTHETIC') >= 1
        assert 'SYNTHETIC' in db.scalar(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='synthetic_studies_data_origin_check'"))


def test_clean_database_reaches_0007_with_structure_and_grants(database_urls):
    name, migrate = new_database(database_urls, 'b3_clean')
    migrate('head')
    engine = create_engine(make_url(database_urls[1]).set(database=name), hide_parameters=True)
    check_structure(engine)
    engine.dispose()


def test_upgrade_from_0006_preserves_old_columns_and_backfills_detected_at(database_urls, synthetic_password, synthetic_password_hash):
    name, migrate = new_database(database_urls, 'b3_upgrade')
    migrate('0006_manual_evaluable')
    engine = create_engine(make_url(database_urls[1]).set(database=name), hide_parameters=True)
    ids = {key: uuid4() for key in ('student', 'enrollment', 'batch', 'snapshot', 'model', 'prediction', 'alert')}
    with engine.begin() as db:
        context = create_context(db, synthetic_password, synthetic_password_hash)
        period, section, actor = context['periods']['real']['id'], context['sections'][0]['id'], context['accounts']['ADMIN']['id']
        db.execute(text("INSERT INTO risk_school.students(id,anon_code,data_origin) VALUES(:id,:code,'REAL')"),
                   {'id': ids['student'], 'code': 'B3-LEGACY-' + uuid4().hex[:10]})
        db.execute(text("INSERT INTO risk_school.enrollments(id,student_id,period_id,section_id,data_origin) VALUES(:id,:s,:p,:g,'REAL')"),
                   {'id': ids['enrollment'], 's': ids['student'], 'p': period, 'g': section})
        db.execute(text("""INSERT INTO risk_school.import_batches(id,period_id,data_origin,created_by,file_name,file_sha256,storage_key)
            VALUES(:id,:p,'REAL',:a,'fixture.csv',repeat('a',64),'fixture.csv')"""), {'id': ids['batch'], 'p': period, 'a': actor})
        db.execute(text("""INSERT INTO risk_school.academic_snapshots(id,enrollment_id,period_id,data_origin,import_batch_id,window_start,
            cutoff_at,available_at,target_date,average_grade,missing_fraction,source_row_number,row_sha256)
            VALUES(:id,:e,:p,'REAL',:b,'2026-01-01','2026-05-01T17:00:00Z','2026-05-01T16:00:00Z','2026-05-02',10,0.8,2,repeat('b',64))"""),
            {'id': ids['snapshot'], 'e': ids['enrollment'], 'p': period, 'b': ids['batch']})
        db.execute(text("""INSERT INTO risk_school.model_versions(id,name,version,algorithm,data_origin,dataset_hash,artifact_sha256,
            artifact_key,feature_schema_version,reference_criterion_version,status,parameters,metrics,manifest)
            VALUES(:id,'legacy','1','DUMMY','REAL',repeat('c',64),repeat('d',64),'k','ml-features-v1','v','DRAFT','{}','{}','{}')"""),
            {'id': ids['model']})
        db.execute(text("""INSERT INTO risk_school.predictions(id,enrollment_id,snapshot_id,model_id,data_origin,risk_level)
            VALUES(:id,:e,:s,:m,'REAL','HIGH')"""), {'id': ids['prediction'], 'e': ids['enrollment'], 's': ids['snapshot'], 'm': ids['model']})
        # Alertas REAL no se crean por la aplicación (bloqueadas): solo para este fixture histórico, sin triggers de usuario.
        db.execute(text('ALTER TABLE risk_school.alerts DISABLE TRIGGER USER'))
        db.execute(text("""INSERT INTO risk_school.alerts(id,enrollment_id,prediction_id,data_origin,severity,opened_at)
            VALUES(:id,:e,:p,'REAL','HIGH','2026-05-02T15:00:00Z')"""), {'id': ids['alert'], 'e': ids['enrollment'], 'p': ids['prediction']})
        db.execute(text('ALTER TABLE risk_school.alerts ENABLE TRIGGER USER'))
    with engine.connect() as db:
        inspector = inspect(db)
        columns = {t: [c['name'] for c in inspector.get_columns(t, schema='risk_school')] for t in inspector.get_table_names(schema='risk_school')}

        def digest(table):
            fields = ','.join(columns[table])
            return db.scalar(text(f"SELECT md5(coalesce(string_agg(to_jsonb(x)::text,'|' ORDER BY id),'')) FROM (SELECT {fields} FROM risk_school.{table}) x"))
        before = {t: digest(t) for t in columns}
    migrate('head')
    with engine.connect() as db:
        assert {t: digest(t) for t in columns} == before  # las columnas anteriores quedan idénticas
        assert db.scalar(text('SELECT detected_at=opened_at FROM risk_school.alerts WHERE id=:id'), {'id': ids['alert']}) is True
        assert db.scalar(text('SELECT as_of_at FROM risk_school.predictions WHERE id=:id'), {'id': ids['prediction']}) is None
        assert_sqlstate(db, 'UPDATE risk_school.predictions SET risk_level=\'LOW\' WHERE id=:id', {'id': ids['prediction']}, '55000')
    engine.dispose()
    owner_engine = create_engine(make_url(database_urls[1]).set(database=name), hide_parameters=True)
    check_structure(owner_engine)
    owner_engine.dispose()
