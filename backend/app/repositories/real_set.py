"""Lectura del conjunto real (ADR 015): referencia vigente por bimestre, su corte y la predicción del modelo REAL activo."""
from sqlalchemy import text

ROWS = """
SELECT s.id AS student_id,s.anon_code,g.grade,g.code AS section_code,e.id AS enrollment_id,
 r.bimester,sn.cutoff_at,sn.average_grade,sn.attendance_pct,sn.activities_pct,sn.behavior_incidents,
 r.risk_level AS reference_risk,r.total_points AS reference_points,pred.risk_level AS predicted_risk,
 (SELECT a.status FROM risk_school.alerts a WHERE a.enrollment_id=e.id AND a.data_origin='REAL'
   ORDER BY a.opened_at DESC,a.id LIMIT 1) AS alert_status
FROM risk_school.enrollments e
JOIN risk_school.students s ON s.id=e.student_id
JOIN risk_school.grade_sections g ON g.id=e.section_id
LEFT JOIN LATERAL (
 SELECT DISTINCT ON (rr.bimester) rr.* FROM risk_school.risk_references rr
 WHERE rr.enrollment_id=e.id AND rr.data_origin='REAL' ORDER BY rr.bimester,rr.revision DESC,rr.id
) r ON true
LEFT JOIN risk_school.academic_snapshots sn ON sn.id=r.snapshot_id AND sn.data_origin='REAL'
LEFT JOIN LATERAL (
 SELECT p.risk_level FROM risk_school.predictions p JOIN risk_school.model_versions m ON m.id=p.model_id
 WHERE p.snapshot_id=sn.id AND p.data_origin='REAL' AND m.data_origin='REAL' AND m.is_active AND m.status='APPROVED'
 ORDER BY p.predicted_at DESC,p.id LIMIT 1
) pred ON true
WHERE e.period_id=:period AND e.data_origin='REAL'
"""


def rows(db, user, period_id, section_id):
    clauses, params = [], {'period': period_id}
    if user.role == 'TUTOR':
        clauses.append('g.tutor_id=:user')
        params['user'] = user.id
    if section_id is not None:
        clauses.append('e.section_id=:section')
        params['section'] = section_id
    sql = ROWS + ''.join(' AND ' + clause for clause in clauses) + ' ORDER BY s.anon_code,s.id,r.bimester NULLS LAST'
    return db.execute(text(sql), params).mappings().all()


def active_algorithm(db):
    return db.scalar(text("""SELECT algorithm FROM risk_school.model_versions
        WHERE data_origin='REAL' AND is_active AND status='APPROVED' LIMIT 1"""))
