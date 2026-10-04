-- Diseño PostgreSQL 17 para la primera demo del sistema de riesgo escolar.
-- Convertir este diseño en una migración Alembic antes de implementar.
-- Este archivo crea objetos en un esquema nuevo. No elimina datos ni crea usuarios.
-- Fase vigente: DEMO. Las seis tablas de investigación se añaden posteriormente.
-- Las escalas 0..20 y 1..3 se usan en datos sintéticos; confirmar escala real antes del piloto.
-- Revisión S0 0.1.1: ver docs/adr/001-arquitectura.md y Conciliacion_SQL_API.md.

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
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
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
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
  is_active boolean NOT NULL DEFAULT true,
  eligible_for_processing boolean NOT NULL DEFAULT false,
  consent_documented boolean NOT NULL DEFAULT false,
  assent_documented boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, data_origin),
  CHECK (data_origin = 'DEMO' OR NOT eligible_for_processing
         OR (consent_documented AND assent_documented))
);

CREATE TABLE enrollments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id uuid NOT NULL,
  period_id uuid NOT NULL,
  section_id uuid NOT NULL REFERENCES grade_sections(id) ON DELETE RESTRICT,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (student_id, data_origin) REFERENCES students(id, data_origin),
  FOREIGN KEY (period_id, data_origin) REFERENCES academic_periods(id, data_origin),
  UNIQUE (student_id, period_id),
  UNIQUE (id, data_origin),
  UNIQUE (id, period_id, data_origin)
);
CREATE INDEX ix_enrollments_period_section ON enrollments(period_id, section_id);

CREATE TABLE import_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  period_id uuid NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
  created_by uuid NOT NULL REFERENCES app_users(id),
  file_name text NOT NULL,
  file_sha256 char(64) NOT NULL CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
  schema_version text NOT NULL DEFAULT 'demo-v1',
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
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
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
  schema_version text NOT NULL DEFAULT 'demo-v1',
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
  name text NOT NULL,
  version text NOT NULL,
  algorithm text NOT NULL CHECK (algorithm IN ('DUMMY','RANDOM_FOREST','SVM','XGBOOST')),
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
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
  -- Guard de esta fase. Retirar solo en una migración que habilite el protocolo REAL.
  CONSTRAINT demo_only_active_model CHECK (NOT is_active OR data_origin = 'DEMO')
);
CREATE UNIQUE INDEX ux_active_model_origin ON model_versions(data_origin) WHERE is_active;

CREATE TABLE predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrollment_id uuid NOT NULL,
  snapshot_id uuid NOT NULL,
  model_id uuid NOT NULL,
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
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
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
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
  data_origin text NOT NULL CHECK (data_origin IN ('DEMO','REAL')),
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
