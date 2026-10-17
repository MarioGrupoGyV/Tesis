"""Registro local M1. En SYNTHETIC el alumno queda elegible (Bloque 1); en REAL nunca."""
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select, text
from app.core.errors import AppError
from app.models.s1 import AcademicPeriod, GradeSection, AppUser, AuditEvent
from app.models.s2 import StudentRecord, EnrollmentRecord, SnapshotRecord
from app.repositories import manual as repo
from app.schemas import manual as schema
from app.schemas.s1 import Period, Section
from app.schemas.s2 import Snapshot
from app.services.students import authorize_student
from app.services.catalogs import require_catalog_role

FEATURES = ('average_grade','attendance_pct','activities_pct','participation_level','behavior_incidents')
LIMA = ZoneInfo('America/Lima')


def require_admin(user):
    if user.role != 'ADMIN':
        raise AppError(403, 'FORBIDDEN', 'Solo ADMIN administra estudiantes y catálogos.')


def conflict(message='El registro cambió. Actualiza la consulta y conserva tu borrador antes de reenviar.'):
    raise AppError(409, 'ACADEMIC_CONFLICT', message)


def version(record, expected):
    if record.version != expected:
        conflict()


def found(record):
    if record is None:
        raise AppError(404, 'ACADEMIC_NOT_FOUND', 'El recurso no está disponible para tu cuenta.')
    return record


def writable(period):
    if period.is_locked:
        conflict('El periodo está bloqueado. Solicita su reapertura al administrador.')


def command(db, user, payload, action, resource_id, model, view, request_id, change):
    digest = sha256((action + ':' + str(resource_id) + ':' + payload.model_dump_json()).encode()).hexdigest()
    prior = repo.prior_command(db, user.id, payload.creation_key)
    if prior:
        if prior.payload['request_digest'] != digest:
            conflict('La clave de envío ya se usó con otro contenido. Revisa el resultado antes de crear un nuevo envío.')
        result = found(db.get(model, prior.entity_id))
    else:
        result = change()
        db.flush()
        db.add(AuditEvent(actor_id=user.id, entity_type=model.__tablename__, entity_id=result.id,
            action=action, request_id=request_id, payload={'creation_key':str(payload.creation_key),
                'request_digest':digest, 'version':getattr(result,'version',getattr(result,'revision',1)),
                'reason':getattr(payload,'reason',None) or getattr(payload,'correction_reason',None)}))
    db.refresh(result)
    output = view.model_validate(result)
    db.commit()
    return output


def tutor(db, id):
    row = found(repo.lock(db, AppUser, id))
    if row.role != 'TUTOR' or not row.is_active:
        raise AppError(422, 'INVALID_TUTOR', 'Selecciona un tutor existente y activo.',
            details=[{'field':'tutor_id','message':'Debe ser un tutor activo.'}])


def catalog_command(db, user, payload, id, kind, request_id):
    require_admin(user)
    model, view = (AcademicPeriod, Period) if kind=='period' else (GradeSection, Section)
    def change():
        row = found(repo.lock(db, model, id)) if id else model()
        values = payload.model_dump(exclude={'creation_key','expected_version'})
        if id:
            version(row, payload.expected_version)
            if repo.has_enrollments(db, model, id):
                structural = ('school_year','start_date','end_date','data_origin') if kind=='period' else ('school_year','grade','code','data_origin')
                if any(getattr(row,key) != values[key] for key in structural):
                    conflict('El catálogo tiene matrículas. Conserva su año, origen y estructura histórica.')
            row.version += 1
        if kind=='section':
            tutor(db, payload.tutor_id)
            if id and db.scalar(select(AcademicPeriod.id).join(EnrollmentRecord,
                EnrollmentRecord.period_id==AcademicPeriod.id).where(EnrollmentRecord.section_id==id,
                AcademicPeriod.is_locked).limit(1)):
                conflict('La sección participa en un periodo bloqueado.')
        for key,value in values.items():
            setattr(row,key,value)
        db.add(row)
        return row
    return command(db,user,payload,'M1_'+kind.upper()+('_UPDATED' if id else '_CREATED'),id,model,view,request_id,change)


def enrollment_context(db, period_id, section_id):
    period = found(repo.lock(db, AcademicPeriod, period_id))
    writable(period)
    section = found(repo.lock(db, GradeSection, section_id))
    from app.repositories.s1 import sections_for_period
    if section.school_year != period.school_year or section.id not in {s.id for s in sections_for_period(db,period)}:
        raise AppError(404,'ACADEMIC_NOT_FOUND','La sección no está disponible en este periodo y origen.')
    if section.data_origin and section.data_origin != period.data_origin:
        conflict('La sección pertenece a otro origen.')
    if section.tutor_id:
        tutor(db,section.tutor_id)
    return period,section


def create_student(db,user,payload,request_id):
    require_admin(user)
    def change():
        period,_ = enrollment_context(db,payload.period_id,payload.section_id)
        student = StudentRecord(anon_code=payload.anon_code,full_name=payload.full_name,data_origin=period.data_origin,
            eligible_for_processing=period.data_origin=='SYNTHETIC',consent_documented=False,assent_documented=False)
        db.add(student)
        db.flush()
        db.add(EnrollmentRecord(student_id=student.id,period_id=period.id,section_id=payload.section_id,data_origin=period.data_origin))
        return student
    return command(db,user,payload,'M1_STUDENT_CREATED',None,StudentRecord,schema.Identity,request_id,change)


def patch_student(db,user,id,payload,request_id):
    require_admin(user)
    def change():
        student = found(repo.lock(db,StudentRecord,id))
        version(student,payload.expected_version)
        if not payload.confirmed or not payload.reason.strip():
            raise AppError(422,'CONFIRMATION_REQUIRED','Confirma el cambio e indica su motivo.')
        periods = db.scalars(select(AcademicPeriod).join(EnrollmentRecord,EnrollmentRecord.period_id==AcademicPeriod.id)
            .where(EnrollmentRecord.student_id==id).order_by(AcademicPeriod.id).with_for_update(of=AcademicPeriod)).all()
        for period in periods:
            writable(period)
        if not student.is_active and not payload.is_active:
            conflict('Reactiva explícitamente al estudiante antes de modificar sus datos.')
        student.full_name=payload.full_name
        student.is_active=payload.is_active
        student.version+=1
        return student
    return command(db,user,payload,'M1_STUDENT_UPDATED',id,StudentRecord,schema.Identity,request_id,change)


def enroll(db,user,payload,request_id):
    require_admin(user)
    def change():
        student=found(repo.lock(db,StudentRecord,payload.student_id))
        if not student.is_active:
            conflict('El estudiante está inactivo. Reactívalo para registrar una matrícula.')
        period,_=enrollment_context(db,payload.period_id,payload.section_id)
        if student.data_origin!=period.data_origin:
            conflict('Alumno y periodo deben conservar el mismo origen.')
        row=EnrollmentRecord(student_id=student.id,period_id=period.id,section_id=payload.section_id,data_origin=period.data_origin)
        if period.data_origin=='SYNTHETIC' and not student.eligible_for_processing:
            student.eligible_for_processing=True
            student.version+=1
        db.add(row)
        return row
    return command(db,user,payload,'M1_ENROLLMENT_CREATED',None,EnrollmentRecord,schema.EnrollmentView,request_id,change)


def patch_enrollment(db,user,id,payload,request_id):
    require_admin(user)
    def change():
        row=found(repo.lock(db,EnrollmentRecord,id))
        version(row,payload.expected_version)
        if not found(repo.lock(db,StudentRecord,row.student_id)).is_active:
            conflict('El estudiante está inactivo.')
        enrollment_context(db,row.period_id,payload.section_id)
        if row.section_id!=payload.section_id and db.scalar(select(SnapshotRecord.id).where(SnapshotRecord.enrollment_id==id).limit(1)):
            conflict('La matrícula tiene mediciones. No se puede cambiar su sección en M1.')
        row.section_id=payload.section_id
        row.version+=1
        return row
    return command(db,user,payload,'M1_ENROLLMENT_UPDATED',id,EnrollmentRecord,schema.EnrollmentView,request_id,change)


def measurement_page(db,user,id,period_id,page,page_size):
    enrollment=authorize_student(db,user,id,period_id)
    rows,total=repo.measurements(db,enrollment.id,page,page_size)
    return schema.MeasurementPage(items=[Snapshot.model_validate(row) for row in rows],total=total,page=page,page_size=page_size)


def create_measurement(db,user,id,period_id,payload,request_id):
    if user.role not in ('ADMIN','TUTOR'):
        raise AppError(403,'FORBIDDEN','Tu rol no registra mediciones.')
    enrollment=authorize_student(db,user,id,period_id)
    def change():
        student=found(repo.lock(db,StudentRecord,id))
        period=found(repo.lock(db,AcademicPeriod,period_id))
        enrollment_locked=found(repo.lock(db,EnrollmentRecord,enrollment.id))
        section=found(repo.lock(db,GradeSection,enrollment_locked.section_id))
        if user.role=='TUTOR' and section.tutor_id!=user.id:
            raise AppError(404,'STUDENT_NOT_FOUND','El estudiante no está disponible en este periodo.')
        writable(period)
        if not student.is_active:
            conflict('El estudiante está inactivo. Sus mediciones se conservan para consulta.')
        cutoff_day=payload.cutoff_at.astimezone(LIMA).date()
        available_day=payload.available_at.astimezone(LIMA).date()
        if not period.start_date<=payload.window_start<=available_day<=cutoff_day<=period.end_date or payload.available_at>payload.cutoff_at or payload.cutoff_at>datetime.now(UTC):
            raise AppError(422,'INVALID_MEASUREMENT_DATES','Revisa ventana, disponibilidad y corte dentro del periodo; no se admiten cortes futuros.',
                details=[{'field':'cutoff_at','message':'Ventana ≤ disponibilidad ≤ corte actual, dentro del periodo.'}])
        availability={}
        for key in FEATURES:
            value=getattr(payload,key)
            at=payload.variable_available_at.get(key,payload.available_at)
            if value is None:
                if key in payload.variable_available_at:
                    raise AppError(422,'INVALID_AVAILABILITY','Una variable sin dato no tiene disponibilidad.')
                continue
            if at>payload.available_at or at.astimezone(LIMA).date()<payload.window_start:
                raise AppError(422,'INVALID_AVAILABILITY','Cada disponibilidad debe estar dentro de la ventana y no superar la fecha común.')
            availability[key]=at.astimezone(UTC).isoformat()
        prior=None
        if payload.supersedes_id:
            prior=found(db.get(SnapshotRecord,payload.supersedes_id))
            if prior.enrollment_id!=enrollment.id:
                raise AppError(404,'ACADEMIC_NOT_FOUND','La medición no está disponible.')
            if prior.revision!=payload.expected_revision or prior.cutoff_at!=payload.cutoff_at:
                conflict('La revisión o el corte cambió. Conserva tu borrador y consulta la revisión actual.')
            if db.scalar(select(SnapshotRecord.id).where(SnapshotRecord.supersedes_id==prior.id)):
                conflict('Esta medición ya tiene una revisión posterior. Consulta la revisión actual.')
        row=SnapshotRecord(enrollment_id=enrollment.id,period_id=period.id,data_origin=period.data_origin,
            window_start=payload.window_start,cutoff_at=payload.cutoff_at.astimezone(UTC),available_at=payload.available_at.astimezone(UTC),target_date=None,
            revision=prior.revision+1 if prior else 1,supersedes_id=prior.id if prior else None,
            entry_channel='MANUAL',purpose=payload.purpose,created_by=user.id,created_at=datetime.now(UTC),
            schema_version='manual-v1',correction_reason=payload.correction_reason,variable_available_at=availability,
            missing_fraction=Decimal(sum(getattr(payload,key) is None for key in FEATURES))/5,
            **{key:getattr(payload,key) for key in FEATURES})
        db.add(row)
        return row
    return command(db,user,payload,'M1_MEASUREMENT_CREATED',enrollment.id,SnapshotRecord,Snapshot,request_id,change)
