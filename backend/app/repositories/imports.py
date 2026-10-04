"""Lecturas observadas y bloqueos de importación, compartidos por preview y commit."""
import hashlib
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models.s1 import AcademicPeriod, AppUser, GradeSection
from app.models.s2 import EnrollmentRecord, ImportBatchRecord, SnapshotRecord, StudentRecord


def advisory_lock(db: Session, namespace: str):
    key = int.from_bytes(hashlib.sha256(namespace.encode()).digest()[:8], "big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def locked_period(db, period_id):
    db.execute(text("SET LOCAL lock_timeout = '10s'"))
    return db.scalar(select(AcademicPeriod).where(AcademicPeriod.id == period_id)
                     .with_for_update(read=True).execution_options(populate_existing=True))


def locked_batch(db, period_id, file_hash):
    advisory_lock(db, f"import:{period_id}:{file_hash}")
    return db.scalar(select(ImportBatchRecord).where(ImportBatchRecord.period_id == period_id,
                     ImportBatchRecord.file_sha256 == file_hash).with_for_update()
                     .execution_options(populate_existing=True))


def observed_records(db, period, rows):
    codes = sorted({r["student_code"] for r in rows})
    # 256 grupos deterministas protegen también códigos aún inexistentes. El orden
    # global evita deadlocks; el límite evita agotar max_locks_per_transaction con
    # 10000 estudiantes. Colisiones solo serializan trabajo adicional.
    stripes = {int.from_bytes(hashlib.sha256(code.encode()).digest()[:2], 'big') % 256 for code in codes}
    for stripe in sorted(stripes):
        advisory_lock(db, f"student-stripe:{stripe}")
    sections = db.scalars(select(GradeSection).where(GradeSection.school_year == period.school_year)
                         .order_by(GradeSection.id).with_for_update(read=True)
                         .execution_options(populate_existing=True)).all()
    tutor_ids = {s.tutor_id for s in sections if s.tutor_id}
    tutors = {u.id: u for u in db.scalars(select(AppUser).where(AppUser.id.in_(tutor_ids))
              .order_by(AppUser.id).with_for_update(read=True).execution_options(populate_existing=True))}
    students = {s.anon_code: s for s in db.scalars(select(StudentRecord).where(StudentRecord.anon_code.in_(codes))
                .order_by(StudentRecord.id).with_for_update().execution_options(populate_existing=True))}
    enrollments = {e.student_id: e for e in db.scalars(select(EnrollmentRecord).where(
        EnrollmentRecord.student_id.in_([s.id for s in students.values()]), EnrollmentRecord.period_id == period.id)
        .order_by(EnrollmentRecord.id).with_for_update().execution_options(populate_existing=True))}
    snapshots = {(s.enrollment_id, s.cutoff_at): s for s in db.scalars(select(SnapshotRecord).where(
        SnapshotRecord.enrollment_id.in_([e.id for e in enrollments.values()]),
        SnapshotRecord.cutoff_at.in_({r['cutoff_at'] for r in rows}))
        .distinct(SnapshotRecord.enrollment_id, SnapshotRecord.cutoff_at)
        .order_by(SnapshotRecord.enrollment_id, SnapshotRecord.cutoff_at, SnapshotRecord.revision.desc()))}
    return {(s.grade, s.code): s for s in sections}, tutors, students, enrollments, snapshots
