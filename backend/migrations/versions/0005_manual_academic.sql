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
CREATE FUNCTION risk_school.deny_manual_prediction() RETURNS trigger LANGUAGE plpgsql
SET search_path=risk_school,pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM academic_snapshots WHERE id=NEW.snapshot_id AND entry_channel='MANUAL') THEN
  RAISE EXCEPTION 'Manual inference is outside M1' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER m1_prediction_guard BEFORE INSERT ON risk_school.predictions
 FOR EACH ROW EXECUTE FUNCTION risk_school.deny_manual_prediction();
REVOKE ALL ON FUNCTION risk_school.check_m1_enrollment(),risk_school.deny_manual_prediction() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION risk_school.check_m1_enrollment(),risk_school.deny_manual_prediction() TO riesgo_app;
