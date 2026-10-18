"""Protocolo REAL (ADR 012): interruptor técnico de ADMIN. No guarda consentimientos, documentos,
autorizadores ni fechas de permiso. En 3B-1 NO está conectado a los guards existentes: toda operación REAL
sigue bloqueada, incluso con el protocolo confirmado."""
from datetime import UTC, datetime
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.core.errors import AppError
from app.models.protocol import ProcessingProtocolRecord
from app.models.s1 import AcademicPeriod, AuditEvent
from app.schemas.protocol import Protocol, ProtocolCreate, ProtocolParams

PARAM_FIELDS = ('school_label', 'cohort_label', 'grade_scale_min', 'grade_scale_max', 'participation_min',
                'participation_max', 'participation_labels', 'bimesters', 'source_label', 'quality_rules',
                'eligibility_rules', 'risk_rule', 'opportune_windows')


def require_admin(user):
    if user.role != 'ADMIN':
        raise AppError(403, 'FORBIDDEN', 'Solo ADMIN administra el protocolo de procesamiento REAL.')


def plain(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value


def params_of(source) -> dict:
    """Parámetros normalizados (para comparar); funciona con un registro o con una entrada."""
    return ProtocolParams.model_validate({field: plain(getattr(source, field)) for field in PARAM_FIELDS}).model_dump(mode='json')


def view(record) -> Protocol:
    values = {field: getattr(record, field) for field in PARAM_FIELDS}
    values.update(id=record.id, period_id=record.period_id, version=record.version, created_at=record.created_at,
                  authorization_confirmed_by_admin=record.authorization_confirmed_by_admin,
                  confirmed_by=record.confirmed_by, confirmed_at=record.confirmed_at)
    return Protocol.model_validate(values)


def audit(db, user, record, action, request_id):
    # Solo identificadores: ni parámetros ni datos personales en el payload.
    db.add(AuditEvent(actor_id=user.id, entity_type='PROCESSING_PROTOCOL', entity_id=record.id, action=action,
                      request_id=request_id, recorded_at=datetime.now(UTC),
                      payload={'protocol_id': str(record.id), 'period_id': str(record.period_id)}))


def locked(db, id):
    record = db.scalar(select(ProcessingProtocolRecord).where(ProcessingProtocolRecord.id == id).with_for_update())
    if record is None:
        raise AppError(404, 'PROTOCOL_NOT_FOUND', 'El protocolo no está disponible.')
    return record


def create(db, user, payload: ProtocolCreate, request_id):
    require_admin(user)
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id == payload.period_id).with_for_update())
    if period is None:
        raise AppError(404, 'PERIOD_NOT_FOUND', 'El periodo no está disponible.')
    if period.data_origin != 'REAL':
        raise AppError(422, 'PROTOCOL_PERIOD_NOT_REAL', 'El protocolo solo se registra para un periodo REAL.')
    for item in payload.bimesters:
        if not period.start_date <= item.start_date or item.close_date > period.end_date:
            raise AppError(422, 'PROTOCOL_OUTSIDE_PERIOD', 'Los bimestres deben quedar dentro del periodo.')
    existing = db.scalar(select(ProcessingProtocolRecord).where(ProcessingProtocolRecord.period_id == period.id)
                         .with_for_update())
    if existing is not None:
        if params_of(existing) != params_of(payload):
            raise AppError(409, 'PROTOCOL_EXISTS', 'El periodo ya tiene un protocolo con otros parámetros.')
        return view(existing), False
    values = {field: plain(getattr(payload, field)) for field in PARAM_FIELDS}
    record = ProcessingProtocolRecord(period_id=period.id, created_by=user.id, **values)
    try:
        db.add(record)
        db.flush()
        audit(db, user, record, 'PROTOCOL_CREATED', request_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, 'PROTOCOL_CONFLICT', 'No se pudo registrar el protocolo; revisa los parámetros.') from None
    db.refresh(record)
    return view(record), True


def by_period(db, user, period_id):
    require_admin(user)
    record = db.scalar(select(ProcessingProtocolRecord).where(ProcessingProtocolRecord.period_id == period_id))
    if record is None:
        raise AppError(404, 'PROTOCOL_NOT_FOUND', 'El periodo no tiene protocolo registrado.')
    return view(record)


def set_authorization(db, user, id, confirmed: bool, request_id):
    """Confirmar o revocar; idempotente: repetir el mismo estado no cambia nada ni audita."""
    require_admin(user)
    record = locked(db, id)
    if record.authorization_confirmed_by_admin == confirmed:
        return view(record), False
    period = db.get(AcademicPeriod, record.period_id)
    if period is None or period.data_origin != 'REAL':
        raise AppError(409, 'PROTOCOL_PERIOD_NOT_REAL', 'El periodo del protocolo ya no es REAL.')
    now = datetime.now(UTC)
    record.authorization_confirmed_by_admin = confirmed
    record.confirmed_by = user.id if confirmed else None
    record.confirmed_at = now if confirmed else None
    record.version += 1
    if confirmed:
        # El protocolo cubre las matrículas ya registradas del periodo: quedan elegibles (activas; nunca se fabrican
        # consentimientos). Revocar las retira (ver abajo) y la elegibilidad efectiva siempre exige el protocolo confirmado.
        db.flush()
        db.execute(text('''UPDATE risk_school.students s SET eligible_for_processing=true, version=version+1
            WHERE s.data_origin='REAL' AND s.is_active AND NOT s.eligible_for_processing
              AND EXISTS(SELECT 1 FROM risk_school.enrollments e WHERE e.student_id=s.id AND e.period_id=:period)'''),
            {'period': record.period_id})
    else:
        # Revocar: los alumnos REAL del periodo dejan de ser elegibles (salvo los cubiertos por otro protocolo confirmado o por la ruta
        # histórica de consentimiento+asentimiento de las fixtures aisladas). No se borra ningún dato; confirmar de nuevo los habilita.
        db.flush()
        db.execute(text('''UPDATE risk_school.students s SET eligible_for_processing=false, version=version+1
            WHERE s.data_origin='REAL' AND s.eligible_for_processing AND NOT (s.consent_documented AND s.assent_documented)
              AND EXISTS(SELECT 1 FROM risk_school.enrollments e WHERE e.student_id=s.id AND e.period_id=:period)
              AND NOT EXISTS(SELECT 1 FROM risk_school.enrollments e2 JOIN risk_school.processing_protocols p ON p.period_id=e2.period_id
                             WHERE e2.student_id=s.id AND p.authorization_confirmed_by_admin)'''),
            {'period': record.period_id})
    audit(db, user, record, 'PROTOCOL_AUTHORIZATION_CONFIRMED' if confirmed else 'PROTOCOL_AUTHORIZATION_REVOKED', request_id)
    db.commit()
    db.refresh(record)
    return view(record), True


def require_real_protocol(db, period):
    """Devuelve el protocolo si está confirmado y cubre el periodo REAL; si no, el bloqueo vigente.

    NO se usa todavía en los guards existentes (3B-2): preparada y probada, sin efecto sobre los flujos."""
    if period is not None and period.data_origin == 'REAL':
        record = db.scalar(select(ProcessingProtocolRecord).where(ProcessingProtocolRecord.period_id == period.id,
            ProcessingProtocolRecord.authorization_confirmed_by_admin.is_(True)))
        if record is not None:
            return record
    raise AppError(422, 'INSTITUTIONAL_PROCESSING_NOT_READY',
        'El procesamiento institucional requiere un protocolo REAL confirmado por un administrador para este periodo.')


def real_student_processable(*, data_origin, is_active, eligible_flag, consent_documented, assent_documented,
                             protocol_confirmed_for_enrollment) -> bool:
    """Elegibilidad (ADR 012, decisión 3B-2): activo + marca de elegibilidad y, en REAL, protocolo confirmado que cubre
    la matrícula. Los consentimientos no se fabrican ni son requisito del sistema (D4); la ruta consentimiento+asentimiento
    solo sobrevive para la evidencia REAL aislada histórica (fixtures ISOLATED_TEST) que la aplicación no crea."""
    if not (is_active and eligible_flag):
        return False
    if data_origin == 'REAL':
        return bool(protocol_confirmed_for_enrollment) or bool(consent_documented and assent_documented)
    return True


def protocol_confirms_period(db, period_id) -> bool:
    return db.scalar(select(ProcessingProtocolRecord.id).where(ProcessingProtocolRecord.period_id == period_id,
        ProcessingProtocolRecord.authorization_confirmed_by_admin.is_(True))) is not None


def mark_eligible_if_covered(db, student, period):
    """REAL: tras crear la matrícula y con protocolo confirmado, el alumno queda elegible (UPDATE; nunca fabrica consentimientos).
    SYNTHETIC no cambia. Debe llamarse después de insertar la matrícula."""
    if period.data_origin == 'REAL' and student.is_active and not student.eligible_for_processing \
            and protocol_confirms_period(db, period.id):
        student.eligible_for_processing = True
        db.flush()
