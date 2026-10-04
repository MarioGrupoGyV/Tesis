from sqlalchemy import select
from app.core.errors import AppError
from app.models.s1 import AcademicPeriod, GradeSection
from app.models.s2 import EnrollmentRecord, SnapshotRecord, StudentRecord
from app.repositories import students as repository
from app.schemas import s2
from app.services.catalogs import require_catalog_role
from app.services.imports import institutional_period


def authorize_period(db, user, period_id, section_id=None):
    require_catalog_role(user)
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise AppError(404, "PERIOD_NOT_FOUND", "El periodo solicitado no existe.")
    from app.repositories.s1 import sections_for_period
    allowed_sections=sections_for_period(db,period,user.id if user.role=='TUTOR' else None)
    if user.role == "TUTOR" and not allowed_sections:
        raise AppError(403, "FORBIDDEN", "No tienes secciones asignadas en este periodo.")
    if section_id:
        section = db.get(GradeSection, section_id)
        if section is None or section.school_year != period.school_year:
            raise AppError(404, "SECTION_NOT_FOUND", "La sección no está disponible en este periodo.")
        if user.role == "TUTOR" and section.tutor_id != user.id:
            raise AppError(403, "FORBIDDEN", "No tienes acceso a esta sección.")
        if section_id not in {section.id for section in allowed_sections}:
            raise AppError(404,'SECTION_NOT_FOUND','La sección no pertenece al contexto de este periodo.')
    institutional_period(period)
    return period


def authorize_student(db, user, student_id, period_id):
    require_catalog_role(user)
    found = db.execute(select(StudentRecord, EnrollmentRecord, GradeSection, AcademicPeriod)
        .join(EnrollmentRecord, EnrollmentRecord.student_id == StudentRecord.id)
        .join(GradeSection, GradeSection.id == EnrollmentRecord.section_id)
        .join(AcademicPeriod, AcademicPeriod.id == EnrollmentRecord.period_id)
        .where(StudentRecord.id == student_id, EnrollmentRecord.period_id == period_id)).first()
    if found is None:
        raise AppError(404, "STUDENT_NOT_FOUND", "El estudiante no está disponible en este periodo.")
    student, enrollment, section, period = found
    if user.role == "TUTOR" and section.tutor_id != user.id:
        raise AppError(403, "FORBIDDEN", "No tienes acceso a este estudiante.")
    institutional_period(period)
    if student.data_origin != period.data_origin or enrollment.data_origin != period.data_origin:
        raise AppError(422, "ORIGIN_NOT_SUPPORTED", "Origen no admitido en este entorno.")
    return enrollment


def list_students(db, user, **filters):
    authorize_period(db, user, filters['period_id'], filters['section_id'])
    rows, total = repository.list_students(db, user, **filters)
    return s2.StudentPage(items=[s2.Student.model_validate(r) for r in rows], total=total,
                          page=filters['page'], page_size=filters['page_size'])


def projection(schema, record):
    return schema.model_validate({key: record[key] for key in schema.model_fields})


def detail(db, user, student_id, period_id):
    enrollment = authorize_student(db, user, student_id, period_id)
    # Fijar los IDs inmutables elegidos en la misma consulta que calcula riesgo.
    # Un commit concurrente no puede mezclar el resumen antiguo con un corte nuevo.
    selected = repository.public_student(db, enrollment.id)
    student = projection(s2.Student, selected)
    snapshot = db.get(SnapshotRecord, selected['_snapshot_id']) if selected['_snapshot_id'] else None
    prediction = repository.selected_prediction(db, selected['_prediction_id']) if selected['_prediction_id'] else None
    alerts, interventions = repository.followup(db, enrollment.id)
    return s2.StudentDetail(student=student, latest_snapshot=s2.Snapshot.model_validate(snapshot) if snapshot else None,
        latest_prediction=projection(s2.Prediction, prediction) if prediction else None,
        alerts=[projection(s2.Alert, a) for a in alerts], interventions=[projection(s2.Intervention, i) for i in interventions])


def timeline(db, user, student_id, period_id, page, page_size):
    enrollment = authorize_student(db, user, student_id, period_id)
    rows, total = repository.timeline(db, enrollment.id, page, page_size)
    return s2.TimelineEventPage(items=[s2.TimelineEvent.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)
