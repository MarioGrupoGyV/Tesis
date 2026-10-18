-- Referencia efectiva M1. Aplicar Alembic 0001–0005, nunca este diseño sobre una base existente.
-- REAL bloqueado; SYNTHETIC es simulación explícita. DEMO histórico se conserva sin nuevas escrituras.
BEGIN;
CREATE SCHEMA risk_school;
SET LOCAL search_path TO risk_school, public;

CREATE TABLE app_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE CHECK (email = lower(email)),
  display_name text NOT NULL,
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('ADMIN','TUTOR','DIRECTOR','RESEARCHER')),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE RESTRICT,
  token_digest char(64) NOT NULL UNIQUE CHECK (token_digest ~ '^[0-9a-f]{64}$'),
  csrf_digest char(64) NOT NULL CHECK (csrf_digest ~ '^[0-9a-f]{64}$'),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (expires_at > created_at)
);
CREATE INDEX ix_sessions_user_expires ON user_sessions(user_id, expires_at);

CREATE TABLE academic_periods (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL,
  school_year smallint NOT NULL CHECK (school_year BETWEEN 2000 AND 2100),
  start_date date NOT NULL,
  end_date date NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  is_locked boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date > start_date),
  UNIQUE (code, data_origin),
  UNIQUE (id, data_origin)
);

CREATE TABLE grade_sections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL,
  grade smallint NOT NULL CHECK (grade BETWEEN 1 AND 5),
  school_year smallint NOT NULL CHECK (school_year BETWEEN 2000 AND 2100),
  tutor_id uuid REFERENCES app_users(id) ON DELETE RESTRICT,
  UNIQUE (grade, code, school_year)
);
CREATE INDEX ix_sections_tutor ON grade_sections(tutor_id);

CREATE TABLE students (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  anon_code text NOT NULL UNIQUE CHECK (length(anon_code) BETWEEN 3 AND 40),
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  is_active boolean NOT NULL DEFAULT true,
  eligible_for_processing boolean NOT NULL DEFAULT false,
  consent_documented boolean NOT NULL DEFAULT false,
  assent_documented boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, data_origin),
  CHECK (data_origin IN ('DEMO','SYNTHETIC') OR NOT eligible_for_processing
         OR (consent_documented AND assent_documented))
);

CREATE TABLE enrollments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id uuid NOT NULL,
  period_id uuid NOT NULL,
  section_id uuid NOT NULL REFERENCES grade_sections(id) ON DELETE RESTRICT,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (student_id, data_origin) REFERENCES students(id, data_origin),
  FOREIGN KEY (period_id, data_origin) REFERENCES academic_periods(id, data_origin),
  UNIQUE (student_id, period_id),
  UNIQUE (id, data_origin),
  UNIQUE (id, period_id, data_origin)
);
CREATE INDEX ix_enrollments_period_section ON enrollments(period_id, section_id);

CREATE TABLE risk_school.synthetic_studies(
        id uuid PRIMARY KEY,
        period_id uuid NOT NULL UNIQUE,
        data_origin text NOT NULL CHECK(data_origin='SYNTHETIC'),
        generator_version text NOT NULL CHECK(generator_version='synthetic-generator-v1'),
        seed bigint NOT NULL CHECK(seed>=0 AND seed<4294967296),
        config jsonb NOT NULL,
        manifest jsonb NOT NULL,
        csv_sha256 char(64) NOT NULL CHECK(csv_sha256 ~ '^[0-9a-f]{64}$'),
        storage_key text NOT NULL UNIQUE CHECK(storage_key ~ '^[0-9a-f]{32}\.json$'),
        payload_sha256 char(64) NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
        bindings jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(bindings)='array'),
        comparison jsonb CHECK(comparison IS NULL OR jsonb_typeof(comparison)='object'),
        created_by uuid NOT NULL REFERENCES risk_school.app_users(id),
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY(period_id,data_origin) REFERENCES risk_school.academic_periods(id,data_origin),
        UNIQUE(id,data_origin), UNIQUE(id,period_id,data_origin,csv_sha256)
    );

CREATE TABLE import_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  study_id uuid,
  period_id uuid NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  created_by uuid NOT NULL REFERENCES app_users(id),
  file_name text NOT NULL,
  file_sha256 char(64) NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
  schema_version text NOT NULL DEFAULT 'academic-v1',
  storage_key text NOT NULL,
  status text NOT NULL DEFAULT 'PREVIEW' CHECK (status IN ('PREVIEW','READY','COMMITTED','FAILED')),
  total_rows integer NOT NULL DEFAULT 0 CHECK (total_rows >= 0),
  valid_rows integer NOT NULL DEFAULT 0 CHECK (valid_rows >= 0),
  invalid_rows integer NOT NULL DEFAULT 0 CHECK (invalid_rows >= 0),
  planned_students integer NOT NULL DEFAULT 0 CHECK (planned_students >= 0),
  planned_enrollments integer NOT NULL DEFAULT 0 CHECK (planned_enrollments >= 0),
  planned_snapshots integer NOT NULL DEFAULT 0 CHECK (planned_snapshots >= 0),
  preview_version integer NOT NULL DEFAULT 1 CHECK (preview_version >= 1),
  preview_state jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(preview_state) = 'array'),
  errors jsonb NOT NULL DEFAULT '[]'::jsonb,
  committed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (valid_rows + invalid_rows = total_rows),
  CHECK (total_rows <= 10000),
  CHECK (planned_students <= valid_rows AND planned_enrollments <= valid_rows
         AND planned_snapshots <= valid_rows),
  CHECK (status <> 'COMMITTED' OR (invalid_rows = 0 AND committed_at IS NOT NULL)),
  FOREIGN KEY (period_id, data_origin) REFERENCES academic_periods(id, data_origin),
  UNIQUE (period_id, file_sha256),
  UNIQUE (id, period_id, data_origin)
);

CREATE TABLE academic_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id uuid NOT NULL,
  period_id uuid NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  import_batch_id uuid NOT NULL,
  window_start date NOT NULL,
  cutoff_at timestamptz NOT NULL,
  available_at timestamptz NOT NULL,
  target_date date NOT NULL,
  revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
  supersedes_id uuid,
  average_grade numeric(5,2) CHECK (average_grade BETWEEN 0 AND 20),
  attendance_pct numeric(5,2) CHECK (attendance_pct BETWEEN 0 AND 100),
  activities_pct numeric(5,2) CHECK (activities_pct BETWEEN 0 AND 100),
  participation_level smallint CHECK (participation_level BETWEEN 1 AND 3),
  behavior_incidents integer CHECK (behavior_incidents >= 0),
  age_years smallint CHECK (age_years BETWEEN 5 AND 25),
  missing_fraction numeric(5,4) NOT NULL CHECK (missing_fraction BETWEEN 0 AND 1),
  schema_version text NOT NULL DEFAULT 'academic-v1',
  source_row_number integer NOT NULL CHECK (source_row_number >= 2),
  row_sha256 char(64) NOT NULL CHECK (row_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (enrollment_id, period_id, data_origin)
    REFERENCES enrollments(id, period_id, data_origin),
  FOREIGN KEY (import_batch_id, period_id, data_origin)
    REFERENCES import_batches(id, period_id, data_origin),
  UNIQUE (enrollment_id, cutoff_at, revision),
  UNIQUE (id, enrollment_id, data_origin),
  UNIQUE (id, enrollment_id, cutoff_at, data_origin),
  FOREIGN KEY (supersedes_id, enrollment_id, cutoff_at, data_origin)
    REFERENCES academic_snapshots(id, enrollment_id, cutoff_at, data_origin),
  CHECK (supersedes_id IS NULL OR supersedes_id <> id),
  CHECK (available_at <= cutoff_at),
  CHECK (window_start <= (cutoff_at AT TIME ZONE 'America/Lima')::date),
  CHECK (target_date > (cutoff_at AT TIME ZONE 'America/Lima')::date)
);
CREATE INDEX ix_snapshots_enrollment_cutoff ON academic_snapshots(enrollment_id, cutoff_at DESC, revision DESC);

CREATE TABLE model_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  study_id uuid,
  name text NOT NULL,
  version text NOT NULL,
  algorithm text NOT NULL CHECK (algorithm IN ('DUMMY','RANDOM_FOREST','SVM','XGBOOST')),
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  dataset_hash char(64) NOT NULL CHECK (dataset_hash ~ '^[0-9a-f]{64}$'),
  artifact_sha256 char(64) NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  artifact_key text NOT NULL,
  feature_schema_version text NOT NULL,
  reference_criterion_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('DRAFT','EVALUATED','APPROVED','RETIRED')),
  is_active boolean NOT NULL DEFAULT false,
  parameters jsonb NOT NULL,
  metrics jsonb NOT NULL,
  manifest jsonb NOT NULL,
  created_by uuid REFERENCES app_users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (name, version, data_origin),
  UNIQUE (id, data_origin),
  CHECK (NOT is_active OR status = 'APPROVED'),
  CONSTRAINT synthetic_only_active_model CHECK(NOT is_active OR COALESCE((data_origin='SYNTHETIC' AND status='APPROVED' AND study_id IS NOT NULL AND manifest->>'scope'='SYNTHETIC_STUDY' AND manifest->>'data_origin'='SYNTHETIC' AND manifest->>'study_id'=study_id::text AND manifest->>'approval_kind'='TECHNICAL_SIMULATION'),false))
);
CREATE UNIQUE INDEX ux_active_model_origin ON model_versions(data_origin) WHERE is_active;

CREATE TABLE predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id uuid NOT NULL,
  snapshot_id uuid NOT NULL,
  model_id uuid NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  risk_level text NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
  probability_low numeric(8,7),
  probability_medium numeric(8,7),
  probability_high numeric(8,7),
  probabilities_calibrated boolean NOT NULL DEFAULT false,
  predicted_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (snapshot_id, enrollment_id, data_origin)
    REFERENCES academic_snapshots(id, enrollment_id, data_origin),
  FOREIGN KEY (model_id, data_origin) REFERENCES model_versions(id, data_origin),
  UNIQUE (snapshot_id, model_id),
  UNIQUE (id, enrollment_id, data_origin),
  CHECK (
    (probability_low IS NULL AND probability_medium IS NULL AND probability_high IS NULL)
    OR
    (probability_low IS NOT NULL AND probability_medium IS NOT NULL AND probability_high IS NOT NULL
     AND probability_low BETWEEN 0 AND 1 AND probability_medium BETWEEN 0 AND 1
     AND probability_high BETWEEN 0 AND 1
     AND abs(probability_low + probability_medium + probability_high - 1) <= 0.00001)
  ),
  CHECK (NOT probabilities_calibrated OR probability_low IS NOT NULL)
);

CREATE TABLE alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id uuid NOT NULL,
  prediction_id uuid NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  assigned_to uuid REFERENCES app_users(id),
  severity text NOT NULL CHECK (severity IN ('MEDIUM','HIGH')),
  status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')),
  resolution_reason text CHECK (length(resolution_reason) <= 1000),
  opened_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz,
  version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  FOREIGN KEY (prediction_id, enrollment_id, data_origin)
    REFERENCES predictions(id, enrollment_id, data_origin),
  UNIQUE (id, enrollment_id, data_origin),
  CHECK (
    (status IN ('OPEN','IN_REVIEW') AND closed_at IS NULL)
    OR (status IN ('RESOLVED','DISMISSED') AND closed_at IS NOT NULL
        AND length(btrim(resolution_reason)) > 0 AND resolution_reason IS NOT NULL)
  )
);
CREATE UNIQUE INDEX ux_active_alert_enrollment ON alerts(enrollment_id) WHERE status IN ('OPEN','IN_REVIEW');
CREATE INDEX ix_alerts_status_severity ON alerts(status, severity, opened_at);

CREATE TABLE interventions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id uuid NOT NULL,
  alert_id uuid,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL','SYNTHETIC')),
  created_by uuid NOT NULL REFERENCES app_users(id),
  kind text NOT NULL CHECK (kind IN ('TUTORING','REINFORCEMENT','FAMILY_MEETING','OTHER')),
  objective text NOT NULL CHECK (length(btrim(objective)) BETWEEN 1 AND 1000),
  status text NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED','DONE','CANCELLED')),
  scheduled_at timestamptz NOT NULL,
  performed_at timestamptz,
  notes text CHECK (length(notes) <= 2000),
  version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (enrollment_id, data_origin) REFERENCES enrollments(id, data_origin),
  FOREIGN KEY (alert_id, enrollment_id, data_origin) REFERENCES alerts(id, enrollment_id, data_origin),
  CHECK ((status = 'DONE' AND performed_at IS NOT NULL) OR (status <> 'DONE' AND performed_at IS NULL))
);
CREATE INDEX ix_interventions_enrollment ON interventions(enrollment_id, scheduled_at);

CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id uuid REFERENCES app_users(id),
  entity_type text NOT NULL,
  entity_id uuid,
  action text NOT NULL,
  request_id uuid NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ix_audit_entity_time ON audit_events(entity_type, entity_id, recorded_at);

-- Evidencias inmutables. El usuario de aplicación no tendrá permisos DDL.
CREATE FUNCTION deny_evidence_mutation() RETURNS trigger LANGUAGE plpgsql
SET search_path = risk_school, pg_catalog AS $$
BEGIN
  RAISE EXCEPTION 'Evidence is immutable; append a revision or an event instead'
    USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER snapshots_immutable BEFORE UPDATE OR DELETE ON academic_snapshots
  FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER predictions_immutable BEFORE UPDATE OR DELETE ON predictions
  FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();
CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION deny_evidence_mutation();

CREATE FUNCTION check_snapshot_period() RETURNS trigger LANGUAGE plpgsql
SET search_path = risk_school, pg_catalog AS $$
DECLARE p academic_periods%ROWTYPE;
BEGIN
  SELECT * INTO STRICT p FROM academic_periods WHERE id = NEW.period_id;
  IF p.is_locked THEN
    RAISE EXCEPTION 'Period is locked' USING ERRCODE = '55000';
  END IF;
  IF NEW.window_start < p.start_date OR NEW.target_date > p.end_date
     OR (NEW.cutoff_at AT TIME ZONE 'America/Lima')::date < p.start_date THEN
    RAISE EXCEPTION 'Snapshot window is outside the academic period' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER snapshot_period_guard BEFORE INSERT ON academic_snapshots
  FOR EACH ROW EXECUTE FUNCTION check_snapshot_period();

CREATE FUNCTION check_followup_change() RETURNS trigger LANGUAGE plpgsql
SET search_path = risk_school, pg_catalog AS $$
DECLARE period_locked boolean;
BEGIN
  SELECT p.is_locked INTO STRICT period_locked FROM enrollments e
    JOIN academic_periods p ON p.id = e.period_id WHERE e.id = NEW.enrollment_id;
  IF period_locked THEN
    RAISE EXCEPTION 'Period is locked' USING ERRCODE = '55000';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.version <> OLD.version + 1 THEN
    RAISE EXCEPTION 'Every followup change must increment version by one' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER alert_change_guard BEFORE INSERT OR UPDATE ON alerts
  FOR EACH ROW EXECUTE FUNCTION check_followup_change();
CREATE TRIGGER intervention_change_guard BEFORE INSERT OR UPDATE ON interventions
  FOR EACH ROW EXECUTE FUNCTION check_followup_change();

ALTER TABLE academic_periods ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE students ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE enrollments ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE import_batches ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE academic_snapshots ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE model_versions ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE predictions ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE alerts ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE interventions ADD CONSTRAINT processing_origin CHECK(data_origin IN ('REAL','SYNTHETIC')) NOT VALID;
ALTER TABLE import_batches ADD CONSTRAINT import_batches_study_origin_fk FOREIGN KEY(study_id,data_origin) REFERENCES synthetic_studies(id,data_origin);
ALTER TABLE import_batches ADD CONSTRAINT import_batches_synthetic_provenance CHECK((data_origin='SYNTHETIC')=(study_id IS NOT NULL));
ALTER TABLE model_versions ADD CONSTRAINT model_versions_study_origin_fk FOREIGN KEY(study_id,data_origin) REFERENCES synthetic_studies(id,data_origin);
ALTER TABLE model_versions ADD CONSTRAINT model_versions_synthetic_provenance CHECK((data_origin='SYNTHETIC')=(study_id IS NOT NULL));
ALTER TABLE import_batches ADD CONSTRAINT import_registered_csv_fk FOREIGN KEY(study_id,period_id,data_origin,file_sha256) REFERENCES synthetic_studies(id,period_id,data_origin,csv_sha256);
CREATE FUNCTION risk_school.check_prediction_study() RETURNS trigger LANGUAGE plpgsql
        SET search_path=risk_school,pg_catalog AS $$
        DECLARE batch_study uuid; model_study uuid;
        BEGIN
          IF NEW.data_origin='SYNTHETIC' THEN
            -- Bloque 1 (0006): MANUAL resuelve el estudio por periodo; CSV, por lote.
            SELECT CASE WHEN s.entry_channel='MANUAL'
                THEN (SELECT st.id FROM synthetic_studies st WHERE st.period_id=s.period_id AND st.data_origin='SYNTHETIC')
                ELSE b.study_id END INTO STRICT batch_study
              FROM academic_snapshots s LEFT JOIN import_batches b ON b.id=s.import_batch_id WHERE s.id=NEW.snapshot_id;
            SELECT study_id INTO STRICT model_study FROM model_versions WHERE id=NEW.model_id;
            IF batch_study IS NULL OR batch_study IS DISTINCT FROM model_study THEN
              RAISE EXCEPTION 'Incompatible study provenance' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END; $$;
CREATE TRIGGER prediction_study_guard BEFORE INSERT ON predictions FOR EACH ROW EXECUTE FUNCTION check_prediction_study();

CREATE FUNCTION risk_school.check_study_evidence() RETURNS trigger LANGUAGE plpgsql
        SET search_path=risk_school,pg_catalog AS $$
        BEGIN
          IF TG_OP='DELETE' OR
             (to_jsonb(NEW)-'bindings'-'comparison') IS DISTINCT FROM (to_jsonb(OLD)-'bindings'-'comparison') OR
             (jsonb_array_length(OLD.bindings)>0 AND NEW.bindings IS DISTINCT FROM OLD.bindings) OR
             (OLD.comparison IS NOT NULL AND NEW.comparison IS DISTINCT FROM OLD.comparison) THEN
            RAISE EXCEPTION 'Study evidence is immutable' USING ERRCODE='55000';
          END IF;
          RETURN NEW;
        END; $$;
CREATE TRIGGER study_evidence_guard BEFORE UPDATE OR DELETE ON synthetic_studies FOR EACH ROW EXECUTE FUNCTION check_study_evidence();
-- S5: migración 0004, decisiones persistentes e idempotencia.

CREATE TABLE risk_school.followup_decisions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 prediction_id uuid NOT NULL UNIQUE,
 enrollment_id uuid NOT NULL,
 data_origin text NOT NULL CHECK(data_origin='SYNTHETIC'),
 study_id uuid NOT NULL,
 alert_id uuid,
 decision text NOT NULL CHECK(decision IN ('CREATED','UPDATED','RETAINED_LOW','NO_ALERT')),
 policy_version text NOT NULL CHECK(policy_version='followup-policy-v1'),
 recorded_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(prediction_id,enrollment_id,data_origin) REFERENCES risk_school.predictions(id,enrollment_id,data_origin),
 FOREIGN KEY(alert_id,enrollment_id,data_origin) REFERENCES risk_school.alerts(id,enrollment_id,data_origin),
 FOREIGN KEY(study_id,data_origin) REFERENCES risk_school.synthetic_studies(id,data_origin),
 CHECK ((decision='NO_ALERT' AND alert_id IS NULL) OR (decision<>'NO_ALERT' AND alert_id IS NOT NULL))
);
CREATE INDEX ix_followup_decisions_alert ON risk_school.followup_decisions(alert_id,recorded_at);
ALTER TABLE risk_school.interventions ADD COLUMN creation_key uuid;
ALTER TABLE risk_school.interventions ADD COLUMN creation_payload_sha256 char(64);
ALTER TABLE risk_school.interventions ADD CONSTRAINT intervention_creation_digest
 CHECK((creation_key IS NULL AND creation_payload_sha256 IS NULL) OR
       (creation_key IS NOT NULL AND creation_payload_sha256 ~ '^[0-9a-f]{64}$'));
CREATE UNIQUE INDEX ux_intervention_actor_creation_key ON risk_school.interventions(created_by,creation_key)
 WHERE creation_key IS NOT NULL;

CREATE FUNCTION risk_school.check_followup_provenance(enrollment_uuid uuid,origin text,prediction_uuid uuid)
 RETURNS void LANGUAGE plpgsql SET search_path=risk_school,pg_catalog AS $$
DECLARE period_origin text; period_uuid uuid; period_locked boolean;
        batch_study uuid; model_study uuid; registered_period uuid; section_matches boolean;
BEGIN
 SELECT p.data_origin,p.id,p.is_locked INTO STRICT period_origin,period_uuid,period_locked
 FROM enrollments e JOIN academic_periods p ON p.id=e.period_id
 WHERE e.id=enrollment_uuid AND e.data_origin=origin FOR SHARE OF p;
 IF origin<>'SYNTHETIC' OR period_origin<>'SYNTHETIC' THEN
   RAISE EXCEPTION 'Institutional followup is blocked' USING ERRCODE='23514';
 END IF;
 IF period_locked THEN RAISE EXCEPTION 'Period is locked' USING ERRCODE='55000'; END IF;
 -- Bloque 1 (0006): MANUAL resuelve el estudio por periodo; CSV, por lote COMMITTED.
 SELECT CASE WHEN sn.entry_channel='MANUAL' THEN pst.id ELSE b.study_id END,m.study_id INTO batch_study,model_study
 FROM predictions pr JOIN academic_snapshots sn ON sn.id=pr.snapshot_id
 LEFT JOIN import_batches b ON b.id=sn.import_batch_id
 LEFT JOIN synthetic_studies pst ON pst.period_id=sn.period_id AND pst.data_origin='SYNTHETIC'
 JOIN model_versions m ON m.id=pr.model_id
 WHERE pr.id=prediction_uuid AND pr.enrollment_id=enrollment_uuid AND pr.data_origin=origin
   AND (sn.entry_channel='MANUAL' OR b.status='COMMITTED');
 SELECT st.period_id INTO registered_period FROM synthetic_studies st WHERE st.id=batch_study;
 IF batch_study IS NULL OR batch_study IS DISTINCT FROM model_study OR registered_period IS DISTINCT FROM period_uuid THEN
   RAISE EXCEPTION 'Incompatible followup provenance' USING ERRCODE='23514';
 END IF;
 SELECT EXISTS(SELECT 1 FROM enrollments e JOIN grade_sections g ON g.id=e.section_id
   JOIN synthetic_studies st ON st.id=batch_study,
   jsonb_array_elements(st.manifest->'context'->'sections') section
   WHERE e.id=enrollment_uuid AND g.school_year=(st.config->>'school_year')::integer
     AND section->>'code'=g.code AND (section->>'grade')::integer=g.grade) INTO section_matches;
 IF NOT section_matches THEN
   RAISE EXCEPTION 'Enrollment outside registered study context' USING ERRCODE='23514';
 END IF;
END; $$;

CREATE OR REPLACE FUNCTION risk_school.check_followup_change() RETURNS trigger LANGUAGE plpgsql
 SET search_path=risk_school,pg_catalog AS $$
DECLARE source_prediction uuid;
BEGIN
 IF TG_TABLE_NAME='alerts' THEN source_prediction:=NEW.prediction_id;
 ELSE
   IF NEW.alert_id IS NULL THEN RAISE EXCEPTION 'Followup requires a case' USING ERRCODE='23514'; END IF;
   SELECT prediction_id INTO STRICT source_prediction FROM alerts WHERE id=NEW.alert_id;
 END IF;
 PERFORM check_followup_provenance(NEW.enrollment_id,NEW.data_origin,source_prediction);
 IF TG_OP='UPDATE' THEN
   IF NEW.version<>OLD.version+1 THEN
     RAISE EXCEPTION 'Every change requires exactly one version increment' USING ERRCODE='23514';
   END IF;
   IF NEW.id<>OLD.id OR NEW.enrollment_id<>OLD.enrollment_id OR NEW.data_origin<>OLD.data_origin THEN
     RAISE EXCEPTION 'Case context is immutable' USING ERRCODE='23514';
   END IF;
   IF TG_TABLE_NAME='alerts' THEN
     IF OLD.status IN ('RESOLVED','DISMISSED') OR NEW.opened_at<>OLD.opened_at
       OR NEW.assigned_to IS DISTINCT FROM OLD.assigned_to THEN
       RAISE EXCEPTION 'Closed case or original assignment is immutable' USING ERRCODE='23514';
     END IF;
     IF OLD.status='IN_REVIEW' AND NEW.status='OPEN' THEN
       RAISE EXCEPTION 'Invalid case transition' USING ERRCODE='23514';
     END IF;
     IF NEW.prediction_id<>OLD.prediction_id AND
       (SELECT (s.cutoff_at,s.revision) FROM predictions p JOIN academic_snapshots s ON s.id=p.snapshot_id WHERE p.id=NEW.prediction_id)
       < (SELECT (s.cutoff_at,s.revision) FROM predictions p JOIN academic_snapshots s ON s.id=p.snapshot_id WHERE p.id=OLD.prediction_id) THEN
       RAISE EXCEPTION 'Case source cannot regress' USING ERRCODE='23514';
     END IF;
   ELSE
     IF OLD.status IN ('DONE','CANCELLED') OR NEW.alert_id IS DISTINCT FROM OLD.alert_id
       OR NEW.created_at<>OLD.created_at OR NEW.created_by<>OLD.created_by
       OR NEW.creation_key IS DISTINCT FROM OLD.creation_key
       OR NEW.creation_payload_sha256 IS DISTINCT FROM OLD.creation_payload_sha256 THEN
       RAISE EXCEPTION 'Terminal activity and creation evidence are immutable' USING ERRCODE='23514';
     END IF;
   END IF;
 ELSE
   IF NEW.version<>1 THEN RAISE EXCEPTION 'Initial version must be one' USING ERRCODE='23514'; END IF;
   IF TG_TABLE_NAME='alerts' THEN
     IF NEW.status<>'OPEN' THEN RAISE EXCEPTION 'Initial case must be open' USING ERRCODE='23514'; END IF;
   ELSE
     IF NEW.status<>'PLANNED' OR NEW.creation_key IS NULL OR NEW.creation_payload_sha256 IS NULL
       OR NOT EXISTS(SELECT 1 FROM alerts WHERE id=NEW.alert_id AND status IN ('OPEN','IN_REVIEW')) THEN
       RAISE EXCEPTION 'New activity requires an active case and creation evidence' USING ERRCODE='23514';
     END IF;
   END IF;
 END IF;
 IF TG_TABLE_NAME='interventions' THEN
   IF NEW.performed_at>statement_timestamp() THEN
     RAISE EXCEPTION 'Performed time cannot be future' USING ERRCODE='23514';
   END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION risk_school.check_followup_decision() RETURNS trigger LANGUAGE plpgsql
 SET search_path=risk_school,pg_catalog AS $$
DECLARE source_study uuid; risk text;
BEGIN
 PERFORM check_followup_provenance(NEW.enrollment_id,NEW.data_origin,NEW.prediction_id);
 SELECT m.study_id,p.risk_level INTO STRICT source_study,risk FROM predictions p
 JOIN model_versions m ON m.id=p.model_id WHERE p.id=NEW.prediction_id;
 IF source_study<>NEW.study_id OR
   (NEW.decision IN ('CREATED','UPDATED') AND risk NOT IN ('MEDIUM','HIGH')) OR
   (NEW.decision IN ('RETAINED_LOW','NO_ALERT') AND risk<>'LOW') THEN
   RAISE EXCEPTION 'Decision does not match public class and study' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER decision_provenance_guard BEFORE INSERT ON risk_school.followup_decisions
 FOR EACH ROW EXECUTE FUNCTION risk_school.check_followup_decision();
CREATE TRIGGER decisions_immutable BEFORE UPDATE OR DELETE ON risk_school.followup_decisions
 FOR EACH ROW EXECUTE FUNCTION risk_school.deny_evidence_mutation();
CREATE TRIGGER alerts_no_delete BEFORE DELETE ON risk_school.alerts
 FOR EACH ROW EXECUTE FUNCTION risk_school.deny_evidence_mutation();
CREATE TRIGGER interventions_no_delete BEFORE DELETE ON risk_school.interventions
 FOR EACH ROW EXECUTE FUNCTION risk_school.deny_evidence_mutation();
REVOKE ALL ON risk_school.followup_decisions FROM PUBLIC;
GRANT SELECT,INSERT ON risk_school.followup_decisions TO riesgo_app;
REVOKE DELETE ON risk_school.alerts,risk_school.interventions FROM riesgo_app;
REVOKE ALL ON FUNCTION risk_school.check_followup_provenance(uuid,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION risk_school.check_followup_decision() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.check_followup_provenance(uuid,text,uuid) TO riesgo_app;
GRANT EXECUTE ON FUNCTION risk_school.check_followup_decision() TO riesgo_app;

COMMIT;

-- También comprobar en servicios: rol del tutor asignado, elegibilidad, cierre del periodo
-- antes de importar/predecir, modelo y esquema compatibles, transiciones de estado,
-- fechas efectivas no futuras, incremento de revisión y cálculo de missing_fraction.
-- Fechas DATE del calendario escolar en America/Lima; instantes TIMESTAMPTZ en UTC.
-- Period.school_year determina el catálogo inicial; section.school_year debe coincidir.
-- Section.code es local al grado (p. ej. A); único por grado/código/año.
-- planned_* son conteos de vista previa, no evidencia de filas confirmadas. Revalidar
-- antes de commit; conflictos de matrículas/revisiones: 409 IMPORT_PREVIEW_STALE.
-- preview_state privado guarda estado esperado por fila/serie; preview_version aumenta
-- al refrescar. Confirmar exige expected_preview_version y comparación transaccional.
-- Revisiones: misma matrícula/corte/origen, revision anterior + 1; serie bajo bloqueo.
-- asignar alerta al tutor activo de la sección o null si no existe, dejando aviso.
-- expected_version se compara en UPDATE WHERE version = expected_version; no basta el trigger.
-- Los cambios operativos y sus audit_events se escriben en la misma transacción.
-- No incluir etiquetas, riesgo predicho ni intervenciones posteriores como features.
-- Extensión posterior: criterios, etiquetas de referencia, señales, protocolo,
-- participantes y mediciones pareadas; diseñar su migración y contratos en T0/T1.
-- S6, 2026-10-11: RETROSPECTIVE_EVALUATION usa diario firmado append-only
-- en el volumen ML privado. No introduce tablas, DDL ni modifica registros
-- académicos; referencia al contrato OpenAPI 0.6.0 y manual retrospectivo.

-- Ampliación M1: DDL aditivo de referencia; se ejecuta mediante Alembic 0005.
ALTER TABLE risk_school.students ADD COLUMN full_name text CHECK(length(full_name) BETWEEN 1 AND 160);
ALTER TABLE risk_school.students ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>=1);
ALTER TABLE risk_school.enrollments ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>=1);
ALTER TABLE risk_school.academic_periods ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>=1);
ALTER TABLE risk_school.grade_sections ADD COLUMN version integer NOT NULL DEFAULT 1 CHECK(version>=1);
ALTER TABLE risk_school.grade_sections ADD COLUMN data_origin text CHECK(data_origin IN ('REAL','SYNTHETIC'));
CREATE UNIQUE INDEX ux_student_normalized_code ON risk_school.students
 (upper(regexp_replace(btrim(normalize(anon_code, NFKC)), '\s+', ' ', 'g')));

ALTER TABLE risk_school.academic_snapshots ALTER COLUMN import_batch_id DROP NOT NULL;
ALTER TABLE risk_school.academic_snapshots ALTER COLUMN source_row_number DROP NOT NULL;
ALTER TABLE risk_school.academic_snapshots ALTER COLUMN row_sha256 DROP NOT NULL;
ALTER TABLE risk_school.academic_snapshots ALTER COLUMN target_date DROP NOT NULL;
ALTER TABLE risk_school.academic_snapshots ADD COLUMN entry_channel text NOT NULL DEFAULT 'CSV'
 CHECK(entry_channel IN ('CSV','MANUAL'));
ALTER TABLE risk_school.academic_snapshots ADD COLUMN purpose text NOT NULL DEFAULT 'PARTIAL'
 CHECK(purpose IN ('PARTIAL','CLOSING_REFERENCE'));
ALTER TABLE risk_school.academic_snapshots ADD COLUMN created_by uuid REFERENCES risk_school.app_users(id);
ALTER TABLE risk_school.academic_snapshots ADD COLUMN correction_reason text;
ALTER TABLE risk_school.academic_snapshots ADD COLUMN variable_available_at jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE risk_school.academic_snapshots DROP CONSTRAINT academic_snapshots_participation_level_check;
ALTER TABLE risk_school.academic_snapshots ADD CONSTRAINT snapshot_participation_scale CHECK
 (participation_level BETWEEN 1 AND CASE WHEN entry_channel='MANUAL' THEN 5 ELSE 3 END);
ALTER TABLE risk_school.academic_snapshots ADD CONSTRAINT snapshot_channel_provenance CHECK (
 (entry_channel='CSV' AND import_batch_id IS NOT NULL AND source_row_number IS NOT NULL
  AND row_sha256 IS NOT NULL AND target_date IS NOT NULL AND purpose='PARTIAL') OR
 (entry_channel='MANUAL' AND import_batch_id IS NULL AND source_row_number IS NULL AND row_sha256 IS NULL
  AND target_date IS NULL AND created_by IS NOT NULL AND schema_version='manual-v1'
  AND (average_grade IS NOT NULL OR attendance_pct IS NOT NULL OR activities_pct IS NOT NULL
       OR participation_level IS NOT NULL OR behavior_incidents IS NOT NULL)
  AND (supersedes_id IS NULL OR length(btrim(correction_reason)) BETWEEN 3 AND 1000)));
CREATE UNIQUE INDEX ux_snapshot_single_successor ON risk_school.academic_snapshots(supersedes_id)
 WHERE supersedes_id IS NOT NULL;
CREATE UNIQUE INDEX ux_m1_actor_creation_key ON risk_school.audit_events(actor_id, (payload->>'creation_key'))
 WHERE action LIKE 'M1_%';

CREATE OR REPLACE FUNCTION risk_school.check_snapshot_period() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
DECLARE p academic_periods%ROWTYPE; prior academic_snapshots%ROWTYPE; item record;
BEGIN
 SELECT * INTO STRICT p FROM academic_periods WHERE id=NEW.period_id FOR SHARE;
 IF p.is_locked THEN RAISE EXCEPTION 'Period is locked' USING ERRCODE='55000'; END IF;
 IF NEW.window_start<p.start_date OR NEW.target_date>p.end_date
 OR (NEW.cutoff_at AT TIME ZONE 'America/Lima')::date NOT BETWEEN p.start_date AND p.end_date THEN
  RAISE EXCEPTION 'Snapshot outside period' USING ERRCODE='23514'; END IF;
 IF NEW.entry_channel='MANUAL' THEN
  IF NOT EXISTS(SELECT 1 FROM enrollments e JOIN students s ON s.id=e.student_id
    WHERE e.id=NEW.enrollment_id AND s.is_active) THEN
   RAISE EXCEPTION 'Inactive student' USING ERRCODE='55000'; END IF;
  IF NEW.cutoff_at>clock_timestamp() OR NEW.available_at>NEW.cutoff_at
     OR (NEW.available_at AT TIME ZONE 'America/Lima')::date<NEW.window_start THEN
   RAISE EXCEPTION 'Invalid manual dates' USING ERRCODE='23514'; END IF;
  IF NEW.supersedes_id IS NOT NULL THEN
   SELECT * INTO STRICT prior FROM academic_snapshots WHERE id=NEW.supersedes_id;
   IF NEW.revision<>prior.revision+1 THEN
    RAISE EXCEPTION 'Invalid revision' USING ERRCODE='23514'; END IF;
  ELSIF NEW.revision<>1 THEN RAISE EXCEPTION 'Invalid first revision' USING ERRCODE='23514'; END IF;
  IF jsonb_typeof(NEW.variable_available_at)<>'object' THEN
   RAISE EXCEPTION 'Invalid availability' USING ERRCODE='23514'; END IF;
  FOR item IN SELECT * FROM jsonb_each_text(NEW.variable_available_at) LOOP
   IF item.key NOT IN ('average_grade','attendance_pct','activities_pct','participation_level','behavior_incidents')
    OR to_jsonb(NEW)->item.key='null'::jsonb OR item.value::timestamptz>NEW.available_at
    OR (item.value::timestamptz AT TIME ZONE 'America/Lima')::date<NEW.window_start THEN
    RAISE EXCEPTION 'Invalid variable availability' USING ERRCODE='23514'; END IF;
  END LOOP;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION risk_school.check_m1_enrollment() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
DECLARE p academic_periods%ROWTYPE; g grade_sections%ROWTYPE; active boolean;
BEGIN
 SELECT * INTO STRICT p FROM academic_periods WHERE id=NEW.period_id FOR SHARE;
 SELECT * INTO STRICT g FROM grade_sections WHERE id=NEW.section_id FOR SHARE;
 SELECT is_active INTO STRICT active FROM students WHERE id=NEW.student_id FOR SHARE;
 IF p.data_origin<>NEW.data_origin THEN
  RAISE EXCEPTION 'Enrollment origin foreign key conflict' USING ERRCODE='23503'; END IF;
 IF p.is_locked OR NOT active THEN RAISE EXCEPTION 'Not writable' USING ERRCODE='55000'; END IF;
 IF g.school_year<>p.school_year OR (g.data_origin IS NOT NULL AND g.data_origin<>NEW.data_origin) THEN
  RAISE EXCEPTION 'Enrollment context conflict' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND NEW.section_id<>OLD.section_id AND
 EXISTS(SELECT 1 FROM academic_snapshots WHERE enrollment_id=OLD.id) THEN
  RAISE EXCEPTION 'History prevents section change' USING ERRCODE='55000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER m1_enrollment_guard BEFORE INSERT OR UPDATE ON risk_school.enrollments
 FOR EACH ROW EXECUTE FUNCTION risk_school.check_m1_enrollment();
-- Bloque 1 (migración 0006_manual_evaluable): MANUAL solo se evalúa en SYNTHETIC; REAL sigue bloqueado.
CREATE FUNCTION risk_school.deny_manual_prediction() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM academic_snapshots sn WHERE sn.id=NEW.snapshot_id AND sn.entry_channel='MANUAL')
    AND NOT EXISTS(SELECT 1 FROM academic_snapshots sn
        JOIN academic_periods p ON p.id=sn.period_id JOIN model_versions m ON m.id=NEW.model_id
        WHERE sn.id=NEW.snapshot_id AND sn.data_origin='SYNTHETIC' AND p.data_origin='SYNTHETIC'
          AND m.data_origin='SYNTHETIC' AND NEW.data_origin='SYNTHETIC') THEN
  RAISE EXCEPTION 'Manual inference requires a SYNTHETIC period and model' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER m1_prediction_guard BEFORE INSERT ON risk_school.predictions
 FOR EACH ROW EXECUTE FUNCTION risk_school.deny_manual_prediction();
REVOKE ALL ON FUNCTION risk_school.check_m1_enrollment(),risk_school.deny_manual_prediction() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.check_m1_enrollment(),risk_school.deny_manual_prediction() TO riesgo_app;

-- ===== Migración 0007_real_protocol (Bloque 3B-1): referencia; el esquema efectivo es la migración Alembic. =====
-- Bloque 3B-1: esquema para el protocolo REAL. SOLO ADITIVA y sin cambiar el comportamiento:
-- ningún CHECK de data_origin de modelos, lotes o predicciones se amplía y check_prediction_study /
-- check_followup_provenance siguen igual (3B-2). El protocolo NO guarda consentimientos, documentos,
-- autorizadores ni fechas de permiso (ADR 012, D4).

-- 1. Protocolo REAL: interruptor técnico y parámetros.
CREATE TABLE risk_school.processing_protocols(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 period_id uuid NOT NULL UNIQUE,
 data_origin text NOT NULL DEFAULT 'REAL' CHECK(data_origin='REAL'),
 school_label text NOT NULL CHECK(length(btrim(school_label)) BETWEEN 1 AND 120),
 cohort_label text NOT NULL CHECK(length(btrim(cohort_label)) BETWEEN 1 AND 120),
 grade_scale_min numeric(5,2) NOT NULL,
 grade_scale_max numeric(5,2) NOT NULL,
 participation_min smallint NOT NULL,
 participation_max smallint NOT NULL,
 participation_labels jsonb CHECK(participation_labels IS NULL OR jsonb_typeof(participation_labels)='object'),
 bimesters jsonb NOT NULL CHECK(jsonb_typeof(bimesters)='array' AND jsonb_array_length(bimesters) BETWEEN 1 AND 8),
 source_label text NOT NULL CHECK(length(btrim(source_label)) BETWEEN 1 AND 160),
 quality_rules jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(quality_rules)='object'),
 eligibility_rules jsonb NOT NULL CHECK(jsonb_typeof(eligibility_rules)='object'),
 risk_rule jsonb NOT NULL CHECK(jsonb_typeof(risk_rule)='object' AND risk_rule->>'version'='RIESGO_V1'),
 opportune_windows jsonb NOT NULL CHECK(jsonb_typeof(opportune_windows)='object'),
 authorization_confirmed_by_admin boolean NOT NULL DEFAULT false,
 confirmed_by uuid REFERENCES risk_school.app_users(id),
 confirmed_at timestamptz,
 version integer NOT NULL DEFAULT 1 CHECK(version>=1),
 created_by uuid NOT NULL REFERENCES risk_school.app_users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(period_id,data_origin) REFERENCES risk_school.academic_periods(id,data_origin),
 CHECK(grade_scale_min<grade_scale_max AND participation_min<participation_max AND participation_min>=0),
 CHECK((authorization_confirmed_by_admin AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
    OR (NOT authorization_confirmed_by_admin AND confirmed_by IS NULL AND confirmed_at IS NULL))
);
CREATE FUNCTION risk_school.protect_confirmed_protocol() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'Processing protocols are never deleted' USING ERRCODE='55000';
 END IF;
 -- Con el protocolo confirmado (o al confirmar/revocar) solo cambian los campos de autorización y la versión.
 IF OLD.authorization_confirmed_by_admin OR NEW.authorization_confirmed_by_admin THEN
  IF (to_jsonb(NEW)-'authorization_confirmed_by_admin'-'confirmed_by'-'confirmed_at'-'version')
     IS DISTINCT FROM (to_jsonb(OLD)-'authorization_confirmed_by_admin'-'confirmed_by'-'confirmed_at'-'version') THEN
   RAISE EXCEPTION 'Confirmed protocol parameters are immutable' USING ERRCODE='55000';
  END IF;
  IF OLD.authorization_confirmed_by_admin AND NEW.authorization_confirmed_by_admin
     AND (NEW.confirmed_by IS DISTINCT FROM OLD.confirmed_by OR NEW.confirmed_at IS DISTINCT FROM OLD.confirmed_at) THEN
   RAISE EXCEPTION 'Confirmation evidence is immutable' USING ERRCODE='55000';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER protocol_guard BEFORE UPDATE OR DELETE ON risk_school.processing_protocols
 FOR EACH ROW EXECUTE FUNCTION risk_school.protect_confirmed_protocol();

-- 2. Riesgo de referencia inmutable (RIESGO_V1). Cada componente se deduce de su insumo y el nivel del total.
CREATE TABLE risk_school.risk_references(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 enrollment_id uuid NOT NULL,
 period_id uuid NOT NULL,
 data_origin text NOT NULL CHECK(data_origin IN ('REAL','SYNTHETIC')),
 snapshot_id uuid NOT NULL,
 bimester text NOT NULL CHECK(length(btrim(bimester)) BETWEEN 1 AND 20),
 rule_version text NOT NULL CHECK(rule_version='RIESGO_V1'),
 closing_date date NOT NULL,
 closing_available_at timestamptz NOT NULL,
 average_grade numeric(5,2) NOT NULL CHECK(average_grade BETWEEN 0 AND 20),
 days_scheduled integer NOT NULL CHECK(days_scheduled>0),
 days_attended integer NOT NULL CHECK(days_attended>=0),
 activities_scheduled integer NOT NULL CHECK(activities_scheduled>0),
 activities_delivered integer NOT NULL CHECK(activities_delivered>=0),
 participation_level smallint NOT NULL CHECK(participation_level BETWEEN 1 AND 5),
 behavior_incidents integer NOT NULL CHECK(behavior_incidents>=0),
 points_grade smallint NOT NULL,
 points_attendance smallint NOT NULL,
 points_activities smallint NOT NULL,
 points_participation smallint NOT NULL,
 points_conduct smallint NOT NULL,
 total_points smallint NOT NULL,
 risk_level text NOT NULL CHECK(risk_level IN ('LOW','MEDIUM','HIGH')),
 revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
 supersedes_id uuid,
 computed_by uuid NOT NULL REFERENCES risk_school.app_users(id),
 computed_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(snapshot_id,rule_version,revision),
 UNIQUE(id,snapshot_id),
 FOREIGN KEY(snapshot_id,enrollment_id,data_origin) REFERENCES risk_school.academic_snapshots(id,enrollment_id,data_origin),
 FOREIGN KEY(enrollment_id,period_id,data_origin) REFERENCES risk_school.enrollments(id,period_id,data_origin),
 FOREIGN KEY(supersedes_id,snapshot_id) REFERENCES risk_school.risk_references(id,snapshot_id),
 CHECK(days_attended<=days_scheduled AND activities_delivered<=activities_scheduled),
 CHECK((revision=1)=(supersedes_id IS NULL)),
 -- Umbrales de RIESGO_V1 (hoja de parámetros de la base): componente de 0 a 2 puntos cada uno.
 CHECK(points_grade=CASE WHEN average_grade<11 THEN 2 WHEN average_grade<14 THEN 1 ELSE 0 END),
 CHECK(points_attendance=CASE WHEN 100*days_attended<80*days_scheduled THEN 2
                              WHEN 100*days_attended<90*days_scheduled THEN 1 ELSE 0 END),
 CHECK(points_activities=CASE WHEN 100*activities_delivered<60*activities_scheduled THEN 2
                              WHEN 100*activities_delivered<80*activities_scheduled THEN 1 ELSE 0 END),
 CHECK(points_participation=CASE WHEN participation_level<=2 THEN 2 WHEN participation_level=3 THEN 1 ELSE 0 END),
 CHECK(points_conduct=CASE WHEN behavior_incidents>=3 THEN 2 WHEN behavior_incidents>=1 THEN 1 ELSE 0 END),
 CHECK(total_points=points_grade+points_attendance+points_activities+points_participation+points_conduct),
 CHECK(risk_level=CASE WHEN total_points>=5 THEN 'HIGH' WHEN total_points>=2 THEN 'MEDIUM' ELSE 'LOW' END)
);
CREATE UNIQUE INDEX ux_risk_reference_single_successor ON risk_school.risk_references(supersedes_id)
 WHERE supersedes_id IS NOT NULL;
CREATE INDEX ix_risk_references_period_bimester ON risk_school.risk_references(period_id,bimester);
CREATE FUNCTION risk_school.check_risk_reference() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
DECLARE target date; prior risk_references%ROWTYPE;
BEGIN
 -- El cierre sirve de objetivo de un corte con fecha objetivo; nunca lo precede ni se publica antes de su fecha.
 SELECT s.target_date INTO target FROM academic_snapshots s WHERE s.id=NEW.snapshot_id;
 IF target IS NULL THEN
  RAISE EXCEPTION 'A risk reference requires a cut with a target date' USING ERRCODE='23514';
 END IF;
 IF NEW.closing_date<target THEN
  RAISE EXCEPTION 'The closing date cannot precede the cut target date' USING ERRCODE='23514';
 END IF;
 IF (NEW.closing_available_at AT TIME ZONE 'America/Lima')::date<NEW.closing_date THEN
  RAISE EXCEPTION 'Closing data cannot be available before the closing date' USING ERRCODE='23514';
 END IF;
 IF NEW.revision>1 THEN
  SELECT * INTO prior FROM risk_references WHERE id=NEW.supersedes_id;
  IF NOT FOUND OR prior.snapshot_id<>NEW.snapshot_id OR prior.rule_version<>NEW.rule_version
     OR prior.revision<>NEW.revision-1 OR prior.bimester<>NEW.bimester THEN
   RAISE EXCEPTION 'A revision must supersede the immediately previous one of the same cut' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER risk_reference_guard BEFORE INSERT ON risk_school.risk_references
 FOR EACH ROW EXECUTE FUNCTION risk_school.check_risk_reference();
CREATE TRIGGER risk_references_immutable BEFORE UPDATE OR DELETE ON risk_school.risk_references
 FOR EACH ROW EXECUTE FUNCTION risk_school.deny_evidence_mutation();

-- 3. Estudio: tipo y protocolo. La tabla conserva su nombre. Los CHECK de origen y generador del estudio
--    (solo SYNTHETIC) NO se amplían todavía; la rama INSTITUTIONAL_STUDY queda preparada para 3B-2.
ALTER TABLE risk_school.synthetic_studies ADD COLUMN kind text NOT NULL DEFAULT 'SYNTHETIC_STUDY'
 CHECK(kind IN ('SYNTHETIC_STUDY','INSTITUTIONAL_STUDY'));
ALTER TABLE risk_school.synthetic_studies ADD COLUMN protocol_id uuid REFERENCES risk_school.processing_protocols(id);
ALTER TABLE risk_school.synthetic_studies ADD CONSTRAINT study_kind_origin_protocol CHECK(
 (kind='SYNTHETIC_STUDY' AND data_origin='SYNTHETIC' AND protocol_id IS NULL) OR
 (kind='INSTITUTIONAL_STUDY' AND data_origin='REAL' AND protocol_id IS NOT NULL));

-- 4. Evaluación retrospectiva: los instantes de registro (predicted_at, opened_at) siguen siendo el momento real;
--    as_of_at/detected_at dicen qué momento simula la evaluación. Normal: as_of_at=predicted_at, detected_at=opened_at.
ALTER TABLE risk_school.predictions ADD COLUMN as_of_at timestamptz;
ALTER TABLE risk_school.alerts ADD COLUMN detected_at timestamptz;
-- Relleno de la columna nueva (no altera las demás evidencias): se pausan solo los triggers de usuario.
ALTER TABLE risk_school.alerts DISABLE TRIGGER USER;
UPDATE risk_school.alerts SET detected_at=opened_at;
ALTER TABLE risk_school.alerts ENABLE TRIGGER USER;
ALTER TABLE risk_school.alerts ALTER COLUMN detected_at SET NOT NULL;
ALTER TABLE risk_school.alerts ADD CONSTRAINT alert_detected_not_after_opened CHECK(detected_at<=opened_at);
ALTER TABLE risk_school.predictions ADD CONSTRAINT prediction_as_of_not_after_predicted CHECK(as_of_at IS NULL OR as_of_at<=predicted_at);
CREATE FUNCTION risk_school.set_retrospective_defaults() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF TG_TABLE_NAME='predictions' THEN NEW.as_of_at:=COALESCE(NEW.as_of_at,NEW.predicted_at);
 ELSE NEW.detected_at:=COALESCE(NEW.detected_at,NEW.opened_at);
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER predictions_retrospective_defaults BEFORE INSERT ON risk_school.predictions
 FOR EACH ROW EXECUTE FUNCTION risk_school.set_retrospective_defaults();
CREATE TRIGGER alerts_retrospective_defaults BEFORE INSERT ON risk_school.alerts
 FOR EACH ROW EXECUTE FUNCTION risk_school.set_retrospective_defaults();

-- 5. Elegibilidad REAL por protocolo confirmado: funciones preparadas y SIN trigger asociado.
--    students_eligibility_check (consentimientos) sigue vigente hasta 3B-2, que lo sustituirá por
--    CREATE TRIGGER ... EXECUTE FUNCTION risk_school.check_real_student_eligibility().
CREATE FUNCTION risk_school.real_protocol_covers_period(period_uuid uuid) RETURNS boolean LANGUAGE sql STABLE
SET search_path=risk_school,pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM processing_protocols WHERE period_id=period_uuid AND authorization_confirmed_by_admin)
$$;
CREATE FUNCTION risk_school.real_student_eligible(student_uuid uuid) RETURNS boolean LANGUAGE sql STABLE
SET search_path=risk_school,pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM enrollments e JOIN processing_protocols p ON p.period_id=e.period_id
                WHERE e.student_id=student_uuid AND e.data_origin='REAL' AND p.authorization_confirmed_by_admin)
$$;
CREATE FUNCTION risk_school.check_real_student_eligibility() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF NEW.data_origin='REAL' AND NEW.eligible_for_processing AND NOT real_student_eligible(NEW.id) THEN
  RAISE EXCEPTION 'A REAL student is eligible only with a confirmed protocol covering an enrollment' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;

-- 6. Privilegios: riesgo_app no recibe DDL, DELETE ni TRUNCATE.
REVOKE ALL ON risk_school.processing_protocols, risk_school.risk_references FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON risk_school.processing_protocols TO riesgo_app;
GRANT SELECT,INSERT ON risk_school.risk_references TO riesgo_app;
REVOKE ALL ON FUNCTION risk_school.protect_confirmed_protocol(),risk_school.check_risk_reference(),
 risk_school.set_retrospective_defaults(),risk_school.real_protocol_covers_period(uuid),
 risk_school.real_student_eligible(uuid),risk_school.check_real_student_eligibility() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.protect_confirmed_protocol(),risk_school.check_risk_reference(),
 risk_school.set_retrospective_defaults(),risk_school.real_protocol_covers_period(uuid),
 risk_school.real_student_eligible(uuid),risk_school.check_real_student_eligibility() TO riesgo_app;
