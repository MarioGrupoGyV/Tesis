from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from app.models.ml import ModelVersion, PredictionRecord
from app.models.s1 import GradeSection
from app.models.s2 import EnrollmentRecord


def models(db,page,page_size):
    total = db.scalar(select(func.count()).select_from(ModelVersion).where(ModelVersion.data_origin.in_(('REAL','SYNTHETIC'))))
    rows = db.scalars(select(ModelVersion).where(ModelVersion.data_origin.in_(('REAL','SYNTHETIC')))
        .order_by(ModelVersion.created_at.desc(),ModelVersion.id).limit(page_size).offset((page-1)*page_size)).all()
    return rows,total


def accessible_prediction(db,user,id):
    query = select(PredictionRecord).join(EnrollmentRecord,EnrollmentRecord.id==PredictionRecord.enrollment_id)
    query = query.join(GradeSection,GradeSection.id==EnrollmentRecord.section_id)
    query = query.where(PredictionRecord.id==id,PredictionRecord.data_origin.in_(('REAL','SYNTHETIC')))
    if user.role=='TUTOR':
        query = query.where(GradeSection.tutor_id==user.id)
    return db.scalar(query)


def select_snapshots(db,period_id,as_of):
    # created_at es el instante de incorporación, distinto de disponibilidad declarada.
    return db.execute(text('''SELECT DISTINCT ON (sn.enrollment_id) sn.*,s.id AS student_id,
        s.eligible_for_processing,s.is_active AS student_active,s.consent_documented,s.assent_documented,g.grade
        FROM risk_school.academic_snapshots sn
        JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
        JOIN risk_school.students s ON s.id=e.student_id
        JOIN risk_school.grade_sections g ON g.id=e.section_id
        WHERE sn.period_id=:period AND sn.data_origin IN ('REAL','SYNTHETIC') AND sn.cutoff_at<=:as_of
          AND sn.available_at<=:as_of AND sn.created_at<=:as_of AND e.created_at<=:as_of AND s.created_at<=:as_of
        ORDER BY sn.enrollment_id,sn.cutoff_at DESC,sn.revision DESC,sn.id'''),
        {'period':period_id,'as_of':as_of}).mappings().all()


def insert_prediction(db,values):
    id = db.scalar(insert(PredictionRecord).values(**values).on_conflict_do_nothing(
        index_elements=['snapshot_id','model_id']).returning(PredictionRecord.id))
    if id is not None:
        return db.get(PredictionRecord,id),True
    # READ COMMITTED ve el commit ganador después de esperar la restricción única.
    row = db.scalar(select(PredictionRecord).where(PredictionRecord.snapshot_id==values['snapshot_id'],
                                                  PredictionRecord.model_id==values['model_id']))
    return row,False
