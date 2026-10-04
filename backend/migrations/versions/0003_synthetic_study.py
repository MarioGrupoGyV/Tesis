"""SYNTHETIC separado; no reetiqueta ni elimina evidencia de S3."""
from alembic import op

revision = '0003_synthetic_study'
down_revision = '0002_institutional_boundary'
branch_labels = None
depends_on = None


def upgrade():
    c = op.get_bind()
    tables = ('academic_periods','students','enrollments','import_batches',
              'academic_snapshots','model_versions','predictions','alerts','interventions')
    for table in tables:
        c.exec_driver_sql(f'ALTER TABLE risk_school.{table} DROP CONSTRAINT institutional_origin')
        c.exec_driver_sql(f'ALTER TABLE risk_school.{table} DROP CONSTRAINT {table}_data_origin_check')
        c.exec_driver_sql(f"ALTER TABLE risk_school.{table} ADD CONSTRAINT {table}_data_origin_check CHECK(data_origin IN ('DEMO','REAL','SYNTHETIC'))")
        # NOT VALID mantiene DEMO histórico sin admitir nuevas escrituras DEMO.
        c.exec_driver_sql(f"ALTER TABLE risk_school.{table} ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID")
        if not c.exec_driver_sql(f"SELECT EXISTS(SELECT 1 FROM risk_school.{table} WHERE data_origin='DEMO')").scalar():
            c.exec_driver_sql(f'ALTER TABLE risk_school.{table} VALIDATE CONSTRAINT processing_origin')
    c.exec_driver_sql('ALTER TABLE risk_school.students DROP CONSTRAINT students_check')
    c.exec_driver_sql("ALTER TABLE risk_school.students ADD CONSTRAINT students_eligibility_check CHECK(data_origin IN ('DEMO','SYNTHETIC') OR NOT eligible_for_processing OR(consent_documented AND assent_documented))")
    c.exec_driver_sql('ALTER TABLE risk_school.model_versions DROP CONSTRAINT demo_only_active_model')
    c.exec_driver_sql('ALTER TABLE risk_school.model_versions DROP CONSTRAINT model_activation_pending')
    c.exec_driver_sql("""CREATE TABLE risk_school.synthetic_studies(
        id uuid PRIMARY KEY,
        period_id uuid NOT NULL UNIQUE,
        data_origin text NOT NULL CHECK(data_origin='SYNTHETIC'),
        generator_version text NOT NULL CHECK(generator_version='synthetic-generator-v1'),
        seed bigint NOT NULL CHECK(seed>=0 AND seed<4294967296),
        config jsonb NOT NULL,
        manifest jsonb NOT NULL,
        csv_sha256 char(64) NOT NULL CHECK(csv_sha256 ~ '^[0-9a-f]{64}$'),
        storage_key text NOT NULL UNIQUE CHECK(storage_key ~ '^[0-9a-f]{32}\\.json$'),
        payload_sha256 char(64) NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
        bindings jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(bindings)='array'),
        comparison jsonb CHECK(comparison IS NULL OR jsonb_typeof(comparison)='object'),
        created_by uuid NOT NULL REFERENCES risk_school.app_users(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY(period_id,data_origin) REFERENCES risk_school.academic_periods(id,data_origin),
        UNIQUE(id,data_origin), UNIQUE(id,period_id,data_origin,csv_sha256)
    )""")
    for table in ('import_batches','model_versions'):
        c.exec_driver_sql(f'ALTER TABLE risk_school.{table} ADD COLUMN study_id uuid')
        c.exec_driver_sql(f'ALTER TABLE risk_school.{table} ADD CONSTRAINT {table}_study_origin_fk FOREIGN KEY(study_id,data_origin) REFERENCES risk_school.synthetic_studies(id,data_origin)')
        c.exec_driver_sql(f"ALTER TABLE risk_school.{table} ADD CONSTRAINT {table}_synthetic_provenance CHECK((data_origin='SYNTHETIC')=(study_id IS NOT NULL)) NOT VALID")
        c.exec_driver_sql(f'ALTER TABLE risk_school.{table} VALIDATE CONSTRAINT {table}_synthetic_provenance')
    c.exec_driver_sql('ALTER TABLE risk_school.import_batches ADD CONSTRAINT import_registered_csv_fk FOREIGN KEY(study_id,period_id,data_origin,file_sha256) REFERENCES risk_school.synthetic_studies(id,period_id,data_origin,csv_sha256)')
    c.exec_driver_sql("""ALTER TABLE risk_school.model_versions ADD CONSTRAINT synthetic_only_active_model
        CHECK(NOT is_active OR COALESCE((data_origin='SYNTHETIC' AND status='APPROVED' AND study_id IS NOT NULL
          AND manifest->>'scope'='SYNTHETIC_STUDY' AND manifest->>'data_origin'='SYNTHETIC'
          AND manifest->>'study_id'=study_id::text AND manifest->>'approval_kind'='TECHNICAL_SIMULATION'),false)) NOT VALID""")
    # Bloquear también modelos de otro estudio que comparten el origen SYNTHETIC.
    c.exec_driver_sql("""CREATE FUNCTION risk_school.check_prediction_study() RETURNS trigger LANGUAGE plpgsql
        SET search_path=risk_school,pg_catalog AS $$
        DECLARE batch_study uuid; model_study uuid;
        BEGIN
          IF NEW.data_origin='SYNTHETIC' THEN
            SELECT b.study_id INTO STRICT batch_study FROM academic_snapshots s
              JOIN import_batches b ON b.id=s.import_batch_id WHERE s.id=NEW.snapshot_id;
            SELECT study_id INTO STRICT model_study FROM model_versions WHERE id=NEW.model_id;
            IF batch_study IS NULL OR batch_study IS DISTINCT FROM model_study THEN
              RAISE EXCEPTION 'Incompatible study provenance' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END; $$""")
    c.exec_driver_sql('CREATE TRIGGER prediction_study_guard BEFORE INSERT ON risk_school.predictions FOR EACH ROW EXECUTE FUNCTION risk_school.check_prediction_study()')
    c.exec_driver_sql('REVOKE ALL ON FUNCTION risk_school.check_prediction_study() FROM PUBLIC')
    c.exec_driver_sql('GRANT EXECUTE ON FUNCTION risk_school.check_prediction_study() TO riesgo_app')
    c.exec_driver_sql("""CREATE FUNCTION risk_school.check_study_evidence() RETURNS trigger LANGUAGE plpgsql
        SET search_path=risk_school,pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' OR
             (to_jsonb(NEW)-'bindings'-'comparison') IS DISTINCT FROM (to_jsonb(OLD)-'bindings'-'comparison') OR
             (jsonb_array_length(OLD.bindings)>0 AND NEW.bindings IS DISTINCT FROM OLD.bindings) OR
             (OLD.comparison IS NOT NULL AND NEW.comparison IS DISTINCT FROM OLD.comparison) THEN
            RAISE EXCEPTION 'Study evidence is immutable' USING ERRCODE='55000';
          END IF;
          RETURN NEW;
        END; $$""")
    c.exec_driver_sql('CREATE TRIGGER study_evidence_guard BEFORE UPDATE OR DELETE ON risk_school.synthetic_studies FOR EACH ROW EXECUTE FUNCTION risk_school.check_study_evidence()')
    c.exec_driver_sql('REVOKE ALL ON FUNCTION risk_school.check_study_evidence() FROM PUBLIC')
    c.exec_driver_sql('GRANT EXECUTE ON FUNCTION risk_school.check_study_evidence() TO riesgo_app')
    c.exec_driver_sql('GRANT SELECT,INSERT,UPDATE ON risk_school.synthetic_studies TO riesgo_app')


def downgrade():
    raise RuntimeError('No se elimina el estudio ni su evidencia mediante downgrade.')
