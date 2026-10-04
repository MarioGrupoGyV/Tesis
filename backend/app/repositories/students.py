"""Proyecciones de lectura: riesgo solo si corresponde al último corte y modelo activo."""
from sqlalchemy import text

FROM_STUDENTS = """
FROM risk_school.students s
JOIN risk_school.enrollments e ON e.student_id=s.id
JOIN risk_school.grade_sections g ON g.id=e.section_id
LEFT JOIN LATERAL (
 SELECT sn.* FROM risk_school.academic_snapshots sn WHERE sn.enrollment_id=e.id
 AND sn.data_origin=e.data_origin AND sn.cutoff_at<=statement_timestamp()
 AND sn.available_at<=statement_timestamp() AND sn.created_at<=statement_timestamp()
 ORDER BY sn.cutoff_at DESC, sn.revision DESC LIMIT 1
) sn ON true
LEFT JOIN risk_school.import_batches ib ON ib.id=sn.import_batch_id
LEFT JOIN LATERAL (
 SELECT m.* FROM risk_school.model_versions m WHERE m.is_active AND m.status='APPROVED'
 AND m.data_origin=e.data_origin AND (e.data_origin<>'SYNTHETIC' OR m.study_id=ib.study_id)
 AND m.created_at<=statement_timestamp()
 LIMIT 1
) current_model ON true
LEFT JOIN LATERAL (
 SELECT p.* FROM risk_school.predictions p JOIN risk_school.model_versions m ON m.id=p.model_id
 WHERE p.snapshot_id=sn.id AND p.data_origin=e.data_origin AND m.data_origin=e.data_origin
 AND m.id=current_model.id AND m.is_active AND m.status='APPROVED'
 AND p.predicted_at<=statement_timestamp()
 ORDER BY p.predicted_at DESC, p.id LIMIT 1
) pred ON true
LEFT JOIN risk_school.alerts a ON a.enrollment_id=e.id AND a.status IN ('OPEN','IN_REVIEW')
"""
STUDENT_COLUMNS = """s.id,s.anon_code,e.id AS enrollment_id,e.period_id,e.section_id,
g.code AS section_code,g.grade,e.data_origin,sn.average_grade,sn.attendance_pct,
sn.cutoff_at AS latest_cutoff_at,pred.risk_level,
CASE WHEN pred.id IS NOT NULL THEN 'EVALUATED'
 WHEN current_model.id IS NOT NULL AND sn.id IS NOT NULL AND (
   ((sn.average_grade IS NULL)::int+(sn.attendance_pct IS NULL)::int+(sn.activities_pct IS NULL)::int+
    (sn.participation_level IS NULL)::int+(sn.behavior_incidents IS NULL)::int)/5.0 >
     (current_model.manifest->'feature_schema'->>'inference_max_missing_fraction')::numeric
   OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(current_model.manifest->'feature_schema'->'required_features') required(name)
      WHERE to_jsonb(sn)->required.name='null'::jsonb)) THEN 'INSUFFICIENT_DATA'
 ELSE 'NOT_EVALUATED' END AS evaluation_status,
a.id AS active_alert_id"""
SORTS = {
    "anon_code": "s.anon_code,s.id,e.id",
    "risk_desc": "CASE pred.risk_level WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END DESC,s.anon_code,s.id,e.id",
    "updated_desc": "sn.cutoff_at DESC NULLS LAST,s.anon_code,s.id,e.id",
}


def list_students(db, user, period_id, section_id, search, risk_level, sort, page, page_size):
    clauses, params = ["e.period_id=:period", "e.data_origin IN ('REAL','SYNTHETIC')"], {"period": period_id}
    if user.role == "TUTOR":
        clauses.append("g.tutor_id=:user")
        params['user'] = user.id
    if section_id is not None:
        clauses.append("e.section_id=:section")
        params['section'] = section_id
    if search:
        clauses.append("s.anon_code ILIKE :search ESCAPE '\\'")
        params['search'] = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    if risk_level:
        clauses.append("pred.risk_level=:risk")
        params['risk'] = risk_level
    source = FROM_STUDENTS + " WHERE " + " AND ".join(clauses)
    total = db.scalar(text('SELECT count(*) ' + source), params)
    rows = db.execute(text('SELECT ' + STUDENT_COLUMNS + source + ' ORDER BY ' + SORTS[sort] + ' LIMIT :limit OFFSET :offset'),
                      {**params, 'limit': page_size, 'offset': (page - 1) * page_size}).mappings().all()
    return rows, total


def public_student(db, enrollment_id):
    return db.execute(text('SELECT ' + STUDENT_COLUMNS + ',sn.id AS _snapshot_id,pred.id AS _prediction_id ' +
                           FROM_STUDENTS + ' WHERE e.id=:id'), {'id': enrollment_id}).mappings().one()


def selected_prediction(db, prediction_id):
    return db.execute(text("""SELECT p.*,s.cutoff_at,s.target_date
        FROM risk_school.predictions p JOIN risk_school.academic_snapshots s ON s.id=p.snapshot_id
        WHERE p.id=:id"""), {'id': prediction_id}).mappings().first()


def followup(db, enrollment_id):
    alerts = db.execute(text("""SELECT a.*,e.student_id,s.anon_code FROM risk_school.alerts a
        JOIN risk_school.enrollments e ON e.id=a.enrollment_id JOIN risk_school.students s ON s.id=e.student_id
        WHERE a.enrollment_id=:id ORDER BY a.opened_at DESC,a.id"""), {'id': enrollment_id}).mappings().all()
    interventions = db.execute(text('SELECT * FROM risk_school.interventions WHERE enrollment_id=:id ORDER BY created_at DESC,id'),
                               {'id': enrollment_id}).mappings().all()
    return alerts, interventions


TIMELINE = """
SELECT id,'SNAPSHOT' AS event_type,created_at AS occurred_at,
 'Corte académico · revisión ' || revision AS summary,id AS entity_id FROM risk_school.academic_snapshots WHERE enrollment_id=:id
UNION ALL
SELECT id,'PREDICTION',predicted_at,'Evaluación registrada',id FROM risk_school.predictions WHERE enrollment_id=:id
UNION ALL
SELECT id,'ALERT',opened_at,'Apertura de alerta',id FROM risk_school.alerts WHERE enrollment_id=:id
 AND NOT EXISTS(SELECT 1 FROM risk_school.audit_events ae WHERE ae.entity_id=alerts.id
   AND ae.entity_type='ALERT' AND ae.action='ALERT_CREATED')
UNION ALL
SELECT id,'INTERVENTION',created_at,'Intervención registrada',id FROM risk_school.interventions WHERE enrollment_id=:id
 AND NOT EXISTS(SELECT 1 FROM risk_school.audit_events ae WHERE ae.entity_id=interventions.id
   AND ae.entity_type='INTERVENTION' AND ae.action='INTERVENTION_CREATED')
UNION ALL
SELECT ae.id,'ALERT',ae.recorded_at,
 CASE ae.action WHEN 'ALERT_CREATED' THEN 'Apertura de alerta'
  WHEN 'ALERT_SOURCE_UPDATED' THEN 'Fuente de alerta actualizada'
  WHEN 'ALERT_LOW_RETAINED' THEN 'Riesgo actual bajo; seguimiento conservado para revisión humana'
  WHEN 'ALERT_STATUS_CHANGED' THEN CASE ae.payload->>'status'
   WHEN 'IN_REVIEW' THEN 'Alerta en revisión' WHEN 'RESOLVED' THEN 'Seguimiento concluido en simulación'
   WHEN 'DISMISSED' THEN 'Alerta descartada' ELSE 'Estado de alerta actualizado' END
  ELSE 'Seguimiento registrado' END,ae.entity_id
 FROM risk_school.audit_events ae JOIN risk_school.alerts a ON a.id=ae.entity_id
 WHERE a.enrollment_id=:id AND ae.entity_type='ALERT'
 AND ae.action IN ('ALERT_CREATED','ALERT_SOURCE_UPDATED','ALERT_LOW_RETAINED','ALERT_STATUS_CHANGED')
UNION ALL
SELECT ae.id,'INTERVENTION',ae.recorded_at,
 CASE ae.action WHEN 'INTERVENTION_CREATED' THEN 'Actividad simulada planificada'
  WHEN 'INTERVENTION_UPDATED' THEN CASE ae.payload->>'status'
   WHEN 'DONE' THEN 'Actividad simulada realizada' WHEN 'CANCELLED' THEN 'Actividad simulada cancelada'
   ELSE 'Actividad simulada actualizada' END ELSE 'Actividad registrada' END,ae.entity_id
 FROM risk_school.audit_events ae JOIN risk_school.interventions i ON i.id=ae.entity_id
 WHERE i.enrollment_id=:id AND ae.entity_type='INTERVENTION'
 AND ae.action IN ('INTERVENTION_CREATED','INTERVENTION_UPDATED')
"""


def timeline(db, enrollment_id, page, page_size):
    params = {'id': enrollment_id, 'limit': page_size, 'offset': (page - 1) * page_size}
    total = db.scalar(text('SELECT count(*) FROM (' + TIMELINE + ') events'), params)
    rows = db.execute(text('SELECT * FROM (' + TIMELINE + ') events ORDER BY occurred_at DESC,id DESC,event_type LIMIT :limit OFFSET :offset'), params).mappings().all()
    return rows, total
