"""Una sola lectura consistente para resumen/CSV, sin multiplicar matrículas."""
from sqlalchemy import text
from app.repositories.students import FROM_STUDENTS, STUDENT_COLUMNS

CASE_COUNTS='''
 count(*) FILTER(WHERE status='OPEN') AS cases_open,
 count(*) FILTER(WHERE status='IN_REVIEW') AS cases_in_review,
 count(*) FILTER(WHERE status='RESOLVED') AS cases_resolved,
 count(*) FILTER(WHERE status='DISMISSED') AS cases_dismissed'''
INTERVENTION_COUNTS='''
 count(*) FILTER(WHERE status='PLANNED') AS interventions_planned,
 count(*) FILTER(WHERE status='DONE') AS interventions_done,
 count(*) FILTER(WHERE status='CANCELLED') AS interventions_cancelled'''


def rows(db,user,period_id,section_id=None,search=None,risk_level=None,evaluation_status=None,alert_status=None,authorized_section_ids=None):
    clauses=["e.period_id=:period","e.data_origin='SYNTHETIC'"]
    params={'period':period_id}
    if authorized_section_ids is not None:
        clauses.append('e.section_id=ANY(CAST(:authorized_section_ids AS uuid[]))')
        params['authorized_section_ids']=authorized_section_ids
    if user.role=='TUTOR':
        clauses.append('g.tutor_id=:actor');params['actor']=user.id
    if section_id is not None:
        clauses.append('e.section_id=:section');params['section']=section_id
    if search:
        clauses.append("s.anon_code ILIKE :search ESCAPE '\\'")
        params['search']='%'+search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
    if risk_level is not None:
        clauses.append('pred.risk_level=:risk');params['risk']=risk_level
    if alert_status is not None:
        clauses.append('EXISTS(SELECT 1 FROM risk_school.alerts af WHERE af.enrollment_id=e.id AND af.status=:alert_status)')
        params['alert_status']=alert_status
    query='SELECT '+STUDENT_COLUMNS+''',a.status AS active_alert_status,
        ac.cases_open,ac.cases_in_review,ac.cases_resolved,ac.cases_dismissed,
        ic.interventions_planned,ic.interventions_done,ic.interventions_cancelled '''+FROM_STUDENTS+'''
        LEFT JOIN LATERAL(SELECT '''+CASE_COUNTS+''' FROM risk_school.alerts ca
          WHERE ca.enrollment_id=e.id AND ca.data_origin=e.data_origin) ac ON true
        LEFT JOIN LATERAL(SELECT '''+INTERVENTION_COUNTS+''' FROM risk_school.interventions ci
          WHERE ci.enrollment_id=e.id AND ci.data_origin=e.data_origin) ic ON true
        WHERE '''+' AND '.join(clauses)
    filter_sql=' WHERE evaluation_status=:evaluation_status' if evaluation_status else ''
    if evaluation_status:
        params['evaluation_status']=evaluation_status
    # JSON aggregation returns generated_at even for zero rows, from this same
    # statement snapshot. Each aggregate lateral yields exactly one enrollment row.
    result=db.execute(text('WITH current_rows AS ('+query+''')
        SELECT statement_timestamp() AS generated_at,
        COALESCE(jsonb_agg(to_jsonb(filtered) ORDER BY filtered.anon_code,filtered.id,filtered.enrollment_id),'[]'::jsonb) AS rows
        FROM (SELECT * FROM current_rows'''+filter_sql+') filtered'),params).mappings().one()
    return result['generated_at'],result['rows']
