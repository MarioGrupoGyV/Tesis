"""Lecturas con alcance SQL y locks por matrícula para seguimiento S5."""
from sqlalchemy import select, text
from app.models.followup import AlertRecord, InterventionRecord, FollowupDecisionRecord
from app.models.s2 import EnrollmentRecord
from app.repositories.students import FROM_STUDENTS, STUDENT_COLUMNS, TIMELINE

REGISTERED_SECTION='''AND EXISTS(SELECT 1 FROM risk_school.synthetic_studies ctx,
    jsonb_array_elements(ctx.manifest->'context'->'sections') registered
    WHERE ctx.period_id=e.period_id AND ctx.data_origin='SYNTHETIC'
      AND (ctx.config->>'school_year')::integer=g.school_year
      AND registered->>'code'=g.code AND (registered->>'grade')::integer=g.grade)'''


def scope(user, prefix='g'):
    return (f' AND {prefix}.tutor_id=:actor', {'actor':user.id}) if user.role=='TUTOR' else ('', {})


def resource(db,user,id,kind='alert'):
    table='alerts' if kind=='alert' else 'interventions'
    suffix,params=scope(user)
    return db.execute(text(f'''SELECT r.id,r.enrollment_id,e.period_id,e.section_id
        FROM risk_school.{table} r JOIN risk_school.enrollments e ON e.id=r.enrollment_id
        JOIN risk_school.grade_sections g ON g.id=e.section_id
        WHERE r.id=:id AND r.data_origin='SYNTHETIC' {REGISTERED_SECTION} {suffix}'''),{**params,'id':id}).mappings().first()


def lock_enrollments(db,period_id,ids=None):
    query=select(EnrollmentRecord).where(EnrollmentRecord.period_id==period_id,
        EnrollmentRecord.data_origin=='SYNTHETIC')
    if ids is not None:
        query=query.where(EnrollmentRecord.id.in_(ids))
    return list(db.scalars(query.order_by(EnrollmentRecord.id).with_for_update()
        .execution_options(populate_existing=True)))


def locked_alert(db,id):
    return db.scalar(select(AlertRecord).where(AlertRecord.id==id).with_for_update()
        .execution_options(populate_existing=True))


def locked_intervention(db,id):
    return db.scalar(select(InterventionRecord).where(InterventionRecord.id==id).with_for_update()
        .execution_options(populate_existing=True))


def current_rows(db,period_id):
    return db.execute(text('SELECT '+STUDENT_COLUMNS+''',sn.id AS _snapshot_id,pred.id AS _prediction_id,
        current_model.id AS _model_id,ib.study_id AS _study_id,ib.status AS _batch_status,
        sn.revision AS _revision,g.tutor_id AS _tutor_id '''+FROM_STUDENTS+
        " WHERE e.period_id=:period AND e.data_origin='SYNTHETIC' ORDER BY e.id"),
        {'period':period_id}).mappings().all()


def decision(db,prediction_id):
    return db.scalar(select(FollowupDecisionRecord).where(FollowupDecisionRecord.prediction_id==prediction_id))


def active_alert(db,enrollment_id):
    return db.scalar(select(AlertRecord).where(AlertRecord.enrollment_id==enrollment_id,
        AlertRecord.status.in_(('OPEN','IN_REVIEW'))).with_for_update()
        .execution_options(populate_existing=True))


def intervention_by_key(db,actor_id,key):
    return db.scalar(select(InterventionRecord).where(InterventionRecord.created_by==actor_id,
        InterventionRecord.creation_key==key))


CASE_COLUMNS='''ca.*,e.student_id,s.anon_code,e.period_id,e.section_id,g.code AS section_code,g.grade,
    u.display_name AS assigned_display_name,pred.risk_level AS current_risk_level,
    CASE WHEN pred.id IS NOT NULL THEN 'EVALUATED'
      WHEN current_model.id IS NOT NULL AND sn.id IS NOT NULL AND (
       ((sn.average_grade IS NULL)::int+(sn.attendance_pct IS NULL)::int+(sn.activities_pct IS NULL)::int+
       (sn.participation_level IS NULL)::int+(sn.behavior_incidents IS NULL)::int)/5.0 >
        (current_model.manifest->'feature_schema'->>'inference_max_missing_fraction')::numeric
       OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(current_model.manifest->'feature_schema'->'required_features') required(name)
        WHERE to_jsonb(sn)->required.name='null'::jsonb)) THEN 'INSUFFICIENT_DATA'
      ELSE 'NOT_EVALUATED' END AS current_evaluation_status,
    sn.cutoff_at AS latest_cutoff_at,sn.id AS _snapshot_id,pred.id AS _prediction_id'''
CASE_SOURCE=FROM_STUDENTS+''' JOIN risk_school.alerts ca ON ca.enrollment_id=e.id
    LEFT JOIN risk_school.app_users u ON u.id=ca.assigned_to'''
SORTS={'anon_code':'s.anon_code,s.id,ca.id',
    'severity_desc':"CASE ca.severity WHEN 'HIGH' THEN 2 ELSE 1 END DESC,s.anon_code,ca.id",
    'updated_desc':'ca.updated_at DESC,ca.id'}


def filter_clauses(user,period_id,section_id=None,status=None,severity=None,search=None):
    suffix,params=scope(user)
    clauses=["e.period_id=:period","ca.data_origin='SYNTHETIC'"]
    params.update(period=period_id)
    for key,value,column in (('section',section_id,'e.section_id'),('status',status,'ca.status'),('severity',severity,'ca.severity')):
        if value is not None:
            clauses.append(column+'=:'+key);params[key]=value
    if search:
        clauses.append("s.anon_code ILIKE :search ESCAPE '\\'")
        params['search']='%'+search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
    return ' WHERE '+' AND '.join(clauses)+suffix,params


def list_alerts(db,user,period_id,section_id,status,severity,search,sort,page,page_size,authorized_section_ids=None):
    where,params=filter_clauses(user,period_id,section_id,status,severity,search)
    if authorized_section_ids is not None:
        where+=' AND e.section_id=ANY(CAST(:authorized_section_ids AS uuid[]))'
        params['authorized_section_ids']=authorized_section_ids
    # Window count and rows have the same PostgreSQL statement snapshot.
    rows=list(db.execute(text('SELECT '+CASE_COLUMNS+',count(*) OVER() AS _total '+CASE_SOURCE+where+
        ' ORDER BY '+SORTS[sort]+' LIMIT :limit OFFSET :offset'),
        {**params,'limit':page_size,'offset':(page-1)*page_size}).mappings())
    total=rows[0]['_total'] if rows else db.scalar(text('SELECT count(*) '+CASE_SOURCE+where),params)
    return rows,total


def public_alert(db,user,id):
    suffix,params=scope(user)
    return db.execute(text('SELECT '+CASE_COLUMNS+CASE_SOURCE+
        " WHERE ca.id=:id AND ca.data_origin='SYNTHETIC' "+REGISTERED_SECTION+suffix),{**params,'id':id}).mappings().first()


def case_interventions(db,alert_id):
    return db.scalars(select(InterventionRecord).where(InterventionRecord.alert_id==alert_id)
        .order_by(InterventionRecord.created_at,InterventionRecord.id)).all()


def case_history(db,enrollment_id,alert_id,limit=100):
    # Project only immutable event summaries, never the internal audit payload.
    query='''SELECT * FROM ('''+TIMELINE+''') ev WHERE
      (event_type='ALERT' AND entity_id=:alert) OR
      (event_type='INTERVENTION' AND entity_id IN
       (SELECT id FROM risk_school.interventions WHERE alert_id=:alert))
      ORDER BY occurred_at DESC,id DESC,event_type LIMIT :limit'''
    rows=db.execute(text(query),{'id':enrollment_id,'alert':alert_id,'limit':limit+1}).mappings().all()
    return rows[:limit],len(rows)>limit
