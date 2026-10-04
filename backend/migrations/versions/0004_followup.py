"""S5: evidencia mínima de decisiones e idempotencia de actividades, sin recreación."""
from alembic import op

revision = '0004_followup'
down_revision = '0003_synthetic_study'
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
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
"""

def upgrade():
    op.get_bind().exec_driver_sql(UPGRADE_SQL)

def downgrade():
    raise RuntimeError('No se elimina evidencia de seguimiento por downgrade.')
