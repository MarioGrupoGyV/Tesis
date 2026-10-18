-- Bloque 3B-2: la cadena evaluación → seguimiento → modelos se generaliza por origen. REAL solo opera con un
-- protocolo confirmado que cubra el periodo (ADR 012). Migración ADITIVA: ningún dato existente cambia.
-- Las tablas import_batches, model_versions, predictions, alerts e interventions ya admitían data_origin 'REAL'
-- (0003); aquí se amplían los CHECK de estudios y decisiones, la procedencia, la regla de modelo activo y los triggers.

-- 1. Estudios: origen y generador. El tipo ya enlaza kind ↔ origen ↔ protocolo (0007).
ALTER TABLE risk_school.synthetic_studies DROP CONSTRAINT synthetic_studies_data_origin_check;
ALTER TABLE risk_school.synthetic_studies ADD CONSTRAINT synthetic_studies_data_origin_check CHECK(data_origin IN ('SYNTHETIC','REAL'));
ALTER TABLE risk_school.synthetic_studies DROP CONSTRAINT synthetic_studies_generator_version_check;
ALTER TABLE risk_school.synthetic_studies ADD CONSTRAINT synthetic_studies_generator_version_check
 CHECK(generator_version IN ('synthetic-generator-v1','institutional-loader-v1'));
ALTER TABLE risk_school.synthetic_studies ADD CONSTRAINT study_kind_generator CHECK(
 (kind='SYNTHETIC_STUDY' AND generator_version='synthetic-generator-v1') OR
 (kind='INSTITUTIONAL_STUDY' AND generator_version='institutional-loader-v1'));

-- 2. Decisiones de seguimiento por origen.
ALTER TABLE risk_school.followup_decisions DROP CONSTRAINT followup_decisions_data_origin_check;
ALTER TABLE risk_school.followup_decisions ADD CONSTRAINT followup_decisions_data_origin_check CHECK(data_origin IN ('SYNTHETIC','REAL'));

-- 3. Procedencia: un lote o modelo SYNTHETIC exige estudio; REAL puede llevarlo (estudio institucional) y la FK
--    compuesta (study_id, data_origin) impide asociar un estudio de otro origen. Los REAL sin estudio son los
--    modelos/lotes aislados de las pruebas históricas (ISOLATED_TEST) y no pueden activarse (ver punto 4).
ALTER TABLE risk_school.import_batches DROP CONSTRAINT import_batches_synthetic_provenance;
ALTER TABLE risk_school.import_batches ADD CONSTRAINT import_batches_processing_provenance CHECK(data_origin<>'SYNTHETIC' OR study_id IS NOT NULL);
ALTER TABLE risk_school.model_versions DROP CONSTRAINT model_versions_synthetic_provenance;
ALTER TABLE risk_school.model_versions ADD CONSTRAINT model_versions_processing_provenance CHECK(data_origin<>'SYNTHETIC' OR study_id IS NOT NULL);

-- 4. Modelo activo: regla por alcance. Un activo por origen (ux_active_model_origin ya existe).
ALTER TABLE risk_school.model_versions DROP CONSTRAINT synthetic_only_active_model;
ALTER TABLE risk_school.model_versions ADD CONSTRAINT active_model_scope CHECK(NOT is_active OR COALESCE((
 status='APPROVED' AND study_id IS NOT NULL AND manifest->>'study_id'=study_id::text AND manifest->>'data_origin'=data_origin AND (
  (data_origin='SYNTHETIC' AND manifest->>'scope'='SYNTHETIC_STUDY' AND manifest->>'approval_kind'='TECHNICAL_SIMULATION') OR
  (data_origin='REAL' AND manifest->>'scope'='INSTITUTIONAL_STUDY' AND manifest->>'approval_kind'='LOCAL_EXPLORATORY'))),false));

-- 5. Predicción: mismo estudio, mismo periodo y protocolo confirmado. REAL nunca con modelo SYNTHETIC ni al revés
--    (FK compuesta (model_id, data_origin) de predictions). Sin estudio en lote ni modelo se conserva la compatibilidad
--    con las pruebas REAL aisladas (ISOLATED_TEST), que no pueden activarse ni producir seguimiento.
CREATE OR REPLACE FUNCTION risk_school.check_prediction_study() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
DECLARE batch_study uuid; model_study uuid; snapshot_period uuid;
BEGIN
  IF NEW.data_origin='SYNTHETIC' THEN
    SELECT CASE WHEN s.entry_channel='MANUAL'
        THEN (SELECT st.id FROM synthetic_studies st WHERE st.period_id=s.period_id AND st.data_origin='SYNTHETIC')
        ELSE b.study_id END INTO STRICT batch_study
      FROM academic_snapshots s LEFT JOIN import_batches b ON b.id=s.import_batch_id WHERE s.id=NEW.snapshot_id;
    SELECT study_id INTO STRICT model_study FROM model_versions WHERE id=NEW.model_id;
    IF batch_study IS NULL OR batch_study IS DISTINCT FROM model_study THEN
      RAISE EXCEPTION 'Incompatible study provenance' USING ERRCODE='23514';
    END IF;
  ELSIF NEW.data_origin='REAL' THEN
    SELECT CASE WHEN s.entry_channel='MANUAL'
        THEN (SELECT st.id FROM synthetic_studies st WHERE st.period_id=s.period_id AND st.data_origin='REAL')
        ELSE b.study_id END, s.period_id INTO STRICT batch_study, snapshot_period
      FROM academic_snapshots s LEFT JOIN import_batches b ON b.id=s.import_batch_id WHERE s.id=NEW.snapshot_id;
    SELECT study_id INTO STRICT model_study FROM model_versions WHERE id=NEW.model_id;
    IF batch_study IS NULL AND model_study IS NULL THEN
      RETURN NEW;  -- evidencia REAL aislada (sin estudio institucional)
    END IF;
    IF model_study IS NULL OR batch_study IS DISTINCT FROM model_study THEN
      RAISE EXCEPTION 'Incompatible study provenance' USING ERRCODE='23514';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM synthetic_studies st WHERE st.id=model_study AND st.kind='INSTITUTIONAL_STUDY'
                   AND st.data_origin='REAL' AND st.period_id=snapshot_period) THEN
      RAISE EXCEPTION 'The study does not cover the snapshot period' USING ERRCODE='23514';
    END IF;
    IF NOT real_protocol_covers_period(snapshot_period) THEN
      RAISE EXCEPTION 'REAL processing requires a confirmed protocol covering the period' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END; $$;

-- 6. Seguimiento: SYNTHETIC como hasta ahora; REAL solo con protocolo confirmado, estudio institucional del periodo
--    y sección REAL. Periodo bloqueado, mismo estudio para lote/modelo y mismo periodo se exigen en ambos orígenes.
CREATE OR REPLACE FUNCTION risk_school.check_followup_provenance(enrollment_uuid uuid,origin text,prediction_uuid uuid)
 RETURNS void LANGUAGE plpgsql SET search_path=risk_school,pg_catalog AS $$
DECLARE period_origin text; period_uuid uuid; period_locked boolean;
        batch_study uuid; model_study uuid; registered_period uuid; section_matches boolean;
BEGIN
 SELECT p.data_origin,p.id,p.is_locked INTO STRICT period_origin,period_uuid,period_locked
 FROM enrollments e JOIN academic_periods p ON p.id=e.period_id
 WHERE e.id=enrollment_uuid AND e.data_origin=origin FOR SHARE OF p;
 IF origin NOT IN ('SYNTHETIC','REAL') OR period_origin<>origin THEN
   RAISE EXCEPTION 'Institutional followup is blocked' USING ERRCODE='23514';
 END IF;
 IF origin='REAL' AND NOT real_protocol_covers_period(period_uuid) THEN
   RAISE EXCEPTION 'Institutional followup is blocked' USING ERRCODE='23514';
 END IF;
 IF period_locked THEN RAISE EXCEPTION 'Period is locked' USING ERRCODE='55000'; END IF;
 SELECT CASE WHEN sn.entry_channel='MANUAL' THEN pst.id ELSE b.study_id END,m.study_id INTO batch_study,model_study
 FROM predictions pr JOIN academic_snapshots sn ON sn.id=pr.snapshot_id
 LEFT JOIN import_batches b ON b.id=sn.import_batch_id
 LEFT JOIN synthetic_studies pst ON pst.period_id=sn.period_id AND pst.data_origin=origin
 JOIN model_versions m ON m.id=pr.model_id
 WHERE pr.id=prediction_uuid AND pr.enrollment_id=enrollment_uuid AND pr.data_origin=origin
   AND (sn.entry_channel='MANUAL' OR b.status='COMMITTED');
 SELECT st.period_id INTO registered_period FROM synthetic_studies st WHERE st.id=batch_study AND st.data_origin=origin;
 IF batch_study IS NULL OR batch_study IS DISTINCT FROM model_study OR registered_period IS DISTINCT FROM period_uuid THEN
   RAISE EXCEPTION 'Incompatible followup provenance' USING ERRCODE='23514';
 END IF;
 IF origin='SYNTHETIC' THEN
  SELECT EXISTS(SELECT 1 FROM enrollments e JOIN grade_sections g ON g.id=e.section_id
    JOIN synthetic_studies st ON st.id=batch_study,
    jsonb_array_elements(st.manifest->'context'->'sections') section
    WHERE e.id=enrollment_uuid AND g.school_year=(st.config->>'school_year')::integer
      AND section->>'code'=g.code AND (section->>'grade')::integer=g.grade) INTO section_matches;
 ELSE
  SELECT EXISTS(SELECT 1 FROM enrollments e JOIN grade_sections g ON g.id=e.section_id
    WHERE e.id=enrollment_uuid AND g.data_origin='REAL') INTO section_matches;
 END IF;
 IF NOT section_matches THEN
   RAISE EXCEPTION 'Enrollment outside registered study context' USING ERRCODE='23514';
 END IF;
END; $$;

-- 7. Elegibilidad REAL: sustituye al CHECK de consentimientos. REAL elegible si hay protocolo confirmado que cubre
--    una matrícula del estudiante. La ruta de consentimiento+asentimiento se conserva SOLO para la evidencia REAL aislada
--    histórica (la aplicación no la crea y nunca fabrica consentimientos). Se evalúa al marcar elegible, no en cada edición.
ALTER TABLE risk_school.students DROP CONSTRAINT students_eligibility_check;
CREATE OR REPLACE FUNCTION risk_school.check_real_student_eligibility() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF NEW.data_origin='REAL' AND NEW.eligible_for_processing
    AND NOT (NEW.consent_documented AND NEW.assent_documented) AND NOT real_student_eligible(NEW.id) THEN
  RAISE EXCEPTION 'A REAL student is eligible only with a confirmed protocol covering an enrollment' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER students_real_eligibility_insert BEFORE INSERT ON risk_school.students
 FOR EACH ROW WHEN (NEW.data_origin='REAL' AND NEW.eligible_for_processing)
 EXECUTE FUNCTION risk_school.check_real_student_eligibility();
CREATE TRIGGER students_real_eligibility_update BEFORE UPDATE OF eligible_for_processing ON risk_school.students
 FOR EACH ROW WHEN (NEW.data_origin='REAL' AND NEW.eligible_for_processing AND NOT OLD.eligible_for_processing)
 EXECUTE FUNCTION risk_school.check_real_student_eligibility();

-- 8. Escala de participación por origen: SYNTHETIC por CSV conserva 1–3; REAL y las mediciones MANUAL admiten 1–5
--    (la escala efectiva de un periodo REAL la fija su protocolo, validada en la importación).
ALTER TABLE risk_school.academic_snapshots DROP CONSTRAINT snapshot_participation_scale;
ALTER TABLE risk_school.academic_snapshots ADD CONSTRAINT snapshot_participation_scale CHECK
 (participation_level BETWEEN 1 AND CASE WHEN entry_channel='MANUAL' OR data_origin='REAL' THEN 5 ELSE 3 END);

REVOKE ALL ON FUNCTION risk_school.check_prediction_study(),risk_school.check_followup_provenance(uuid,text,uuid),
 risk_school.check_real_student_eligibility() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.check_prediction_study(),risk_school.check_followup_provenance(uuid,text,uuid),
 risk_school.check_real_student_eligibility() TO riesgo_app;
