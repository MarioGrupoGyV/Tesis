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
