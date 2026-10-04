-- Referencia efectiva S3.1. Aplicar Alembic 0001/0002/0003, nunca este diseño sobre una base existente.
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
            SELECT b.study_id INTO STRICT batch_study FROM academic_snapshots s
              JOIN import_batches b ON b.id=s.import_batch_id WHERE s.id=NEW.snapshot_id;
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
 SELECT b.study_id,m.study_id,st.period_id INTO batch_study,model_study,registered_period
 FROM predictions pr JOIN academic_snapshots sn ON sn.id=pr.snapshot_id
 JOIN import_batches b ON b.id=sn.import_batch_id
 JOIN model_versions m ON m.id=pr.model_id JOIN synthetic_studies st ON st.id=b.study_id
 WHERE pr.id=prediction_uuid AND pr.enrollment_id=enrollment_uuid AND pr.data_origin=origin
   AND b.status='COMMITTED';
 IF batch_study IS NULL OR batch_study IS DISTINCT FROM model_study OR registered_period<>period_uuid THEN
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
