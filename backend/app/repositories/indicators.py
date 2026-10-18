"""Lecturas SQL parametrizadas para indicadores; todo acotado a secciones y a un corte as_of."""
from sqlalchemy import text

STUDENT_ROWS = '''
SELECT e.id AS enrollment_id,s.anon_code,s.is_active,s.eligible_for_processing,e.section_id,
  g.code AS section_code,g.grade,sn.id AS snapshot_id,sn.entry_channel,sn.average_grade,sn.attendance_pct,
  pr.risk_level AS predicted_risk,al.id AS alert_id,al.opened_at AS alert_opened_at,al.detected_at AS alert_detected_at,
  COALESCE(iv.done,0) AS nia,iv.first_done_after_alert
FROM risk_school.enrollments e
JOIN risk_school.students s ON s.id=e.student_id
JOIN risk_school.grade_sections g ON g.id=e.section_id
LEFT JOIN LATERAL (
  SELECT x.* FROM risk_school.academic_snapshots x WHERE x.enrollment_id=e.id AND x.data_origin=e.data_origin
    AND x.cutoff_at<=:as_of AND x.available_at<=:as_of AND (NOT :strict OR x.created_at<=:as_of)
    AND (CAST(:target AS date) IS NULL OR x.target_date=CAST(:target AS date))
  ORDER BY x.cutoff_at DESC,x.revision DESC LIMIT 1) sn ON true
LEFT JOIN LATERAL (
  SELECT p.* FROM risk_school.predictions p WHERE p.snapshot_id=sn.id AND COALESCE(p.as_of_at,p.predicted_at)<=:as_of
  ORDER BY p.predicted_at DESC,p.id LIMIT 1) pr ON true
LEFT JOIN LATERAL (
  SELECT a.* FROM risk_school.alerts a WHERE a.enrollment_id=e.id AND a.detected_at<=:as_of
  ORDER BY a.detected_at,a.id LIMIT 1) al ON true
LEFT JOIN LATERAL (
  SELECT count(*) FILTER (WHERE i.status='DONE' AND i.performed_at<=:as_of AND i.created_at<=:as_of) AS done,
    min(i.performed_at) FILTER (WHERE i.status='DONE' AND i.performed_at<=:as_of AND i.created_at<=:as_of
      AND al.opened_at IS NOT NULL AND i.performed_at>=al.opened_at) AS first_done_after_alert
  FROM risk_school.interventions i WHERE i.enrollment_id=e.id) iv ON true
WHERE e.period_id=:period AND e.data_origin=:origin AND (NOT :strict OR e.created_at<=:as_of)
  AND e.section_id=ANY(CAST(:sections AS uuid[]))
ORDER BY s.anon_code,e.id'''


def student_rows(db, period_id, as_of, section_ids, origin='SYNTHETIC', target_date=None):
    # REAL (evaluación retrospectiva): los datos se incorporan después de los hechos; rige available_at <= as_of, no created_at.
    return db.execute(text(STUDENT_ROWS), {'period': period_id, 'as_of': as_of, 'sections': list(section_ids),
        'origin': origin, 'strict': origin == 'SYNTHETIC', 'target': target_date}).mappings().all()


def batch_totals(db, period_id, as_of, origin='SYNTHETIC'):
    """Lotes recibidos hasta as_of y snapshots CSV confirmados por elegibilidad del estudiante."""
    batches = db.execute(text('''SELECT
        COALESCE(sum(total_rows),0) AS received,COALESCE(sum(invalid_rows),0) AS rejected,
        COALESCE(sum(valid_rows) FILTER (WHERE status<>'COMMITTED'),0) AS valid_not_committed
        FROM risk_school.import_batches WHERE period_id=:period AND data_origin=:origin AND created_at<=:as_of'''),
        {'period': period_id, 'as_of': as_of, 'origin': origin}).mappings().one()
    processed = db.execute(text('''SELECT
        count(*) FILTER (WHERE s.eligible_for_processing) AS eligible,
        count(*) FILTER (WHERE NOT s.eligible_for_processing) AS ineligible
        FROM risk_school.academic_snapshots sn
        JOIN risk_school.import_batches b ON b.id=sn.import_batch_id
        JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
        JOIN risk_school.students s ON s.id=e.student_id
        WHERE b.period_id=:period AND b.status='COMMITTED' AND b.committed_at<=:as_of'''),
        {'period': period_id, 'as_of': as_of}).mappings().one()
    manual = db.scalar(text('''SELECT count(*) FROM risk_school.academic_snapshots sn
        WHERE sn.period_id=:period AND sn.entry_channel='MANUAL' AND sn.created_at<=:as_of'''),
        {'period': period_id, 'as_of': as_of})
    return batches, processed, manual


INTERVENTION_ROWS = """
SELECT i.id AS intervention_id,i.alert_id,i.performed_at,s.anon_code,e.section_id,g.code AS section_code,g.grade,
  a.opened_at AS alert_opened_at
FROM risk_school.interventions i
JOIN risk_school.enrollments e ON e.id=i.enrollment_id
JOIN risk_school.students s ON s.id=e.student_id
JOIN risk_school.grade_sections g ON g.id=e.section_id
LEFT JOIN risk_school.alerts a ON a.id=i.alert_id AND a.detected_at<=:as_of
WHERE e.period_id=:period AND e.data_origin=:origin AND (NOT :strict OR e.created_at<=:as_of)
  AND e.section_id=ANY(CAST(:sections AS uuid[]))
  AND s.is_active AND s.eligible_for_processing
  AND i.status='DONE' AND i.performed_at<=:as_of AND i.created_at<=:as_of
ORDER BY s.anon_code,i.performed_at,i.id"""


def intervention_rows(db, period_id, as_of, section_ids, origin='SYNTHETIC'):
    """Intervenciones realizadas de estudiantes elegibles; la alerta ligada solo cuenta si ya existía en as_of."""
    return db.execute(text(INTERVENTION_ROWS), {'period': period_id, 'as_of': as_of, 'sections': list(section_ids),
        'origin': origin, 'strict': origin == 'SYNTHETIC'}).mappings().all()
