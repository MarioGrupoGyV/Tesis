-- Bloque 1: una medición MANUAL puede evaluarse solo en simulación. REAL conserva el bloqueo.
-- Sustituye el cuerpo de la función; el trigger m1_prediction_guard y los grants se conservan.
CREATE OR REPLACE FUNCTION risk_school.deny_manual_prediction() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM academic_snapshots sn
            WHERE sn.id=NEW.snapshot_id AND sn.entry_channel='MANUAL')
    AND NOT EXISTS(SELECT 1 FROM academic_snapshots sn
        JOIN academic_periods p ON p.id=sn.period_id
        JOIN model_versions m ON m.id=NEW.model_id
        WHERE sn.id=NEW.snapshot_id AND sn.data_origin='SYNTHETIC' AND p.data_origin='SYNTHETIC'
          AND m.data_origin='SYNTHETIC' AND NEW.data_origin='SYNTHETIC') THEN
  RAISE EXCEPTION 'Manual inference requires a SYNTHETIC period and model' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION risk_school.deny_manual_prediction() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.deny_manual_prediction() TO riesgo_app;
-- La procedencia de estudio de una medición MANUAL se resuelve por el periodo (no hay lote).
-- Sigue exigiendo que el estudio del modelo coincida exactamente; CSV conserva el cálculo por lote.
CREATE OR REPLACE FUNCTION risk_school.check_prediction_study() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
DECLARE batch_study uuid; model_study uuid;
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
  END IF;
  RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION risk_school.check_prediction_study() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.check_prediction_study() TO riesgo_app;
-- Seguimiento: la procedencia de una predicción MANUAL se verifica por el estudio del periodo.
-- El resto de verificaciones (SYNTHETIC, periodo desbloqueado, sección del contexto) no cambia.
CREATE OR REPLACE FUNCTION risk_school.check_followup_provenance(enrollment_uuid uuid,origin text,prediction_uuid uuid)
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
REVOKE ALL ON FUNCTION risk_school.check_followup_provenance(uuid,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.check_followup_provenance(uuid,text,uuid) TO riesgo_app;
