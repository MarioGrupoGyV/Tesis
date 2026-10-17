"""Consultas y bloqueos M1; no expone credenciales ni elegibilidad."""
from sqlalchemy import select, func, text
from app.models.s1 import AcademicPeriod, GradeSection, AuditEvent
from app.models.s2 import StudentRecord, EnrollmentRecord, SnapshotRecord


def lock(db, model, id):
    return db.scalar(select(model).where(model.id == id).with_for_update())


def prior_command(db, actor, key):
    db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': f'm1:{actor}:{key}'})
    return db.scalar(select(AuditEvent).where(AuditEvent.actor_id == actor,
        AuditEvent.action.like('M1_%'), AuditEvent.payload['creation_key'].astext == str(key)))


def measurements(db, enrollment_id, page, page_size):
    where = SnapshotRecord.enrollment_id == enrollment_id
    total = db.scalar(select(func.count()).select_from(SnapshotRecord).where(where))
    rows = db.scalars(select(SnapshotRecord).where(where).order_by(SnapshotRecord.cutoff_at.desc(),
        SnapshotRecord.revision.desc(), SnapshotRecord.id).limit(page_size).offset((page-1)*page_size)).all()
    return rows, total


def identities(db, search):
    escaped = search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
    return db.scalars(select(StudentRecord).where(StudentRecord.anon_code.ilike('%'+escaped+'%', escape='\\') |
        StudentRecord.full_name.ilike('%'+escaped+'%', escape='\\')).order_by(StudentRecord.anon_code).limit(20)).all()


def has_enrollments(db, model, id):
    column = EnrollmentRecord.period_id if model is AcademicPeriod else EnrollmentRecord.section_id
    return bool(db.scalar(select(EnrollmentRecord.id).where(column == id).limit(1)))
