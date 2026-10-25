"""Persistencia del riesgo de referencia: el backend calcula nivel y componentes a partir de los insumos de cierre;
el cliente nunca los envía. Inmutable: una corrección inserta otra revisión de la misma regla.

Regla de un periodo (ADR 013): la de su protocolo REAL (`risk_rule.version`, congelada al confirmarlo); sin protocolo,
la regla activa `ACTIVE_RULE_VERSION` (RIESGO_V2). V1 y V2 conviven como filas distintas de la tabla.

Sin endpoint público en 3B-1; lo usan pruebas y la CLI interna `infra/load_closings.py`."""
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.core.errors import AppError
from app.models.s1 import AuditEvent
from app.models.s2 import SnapshotRecord
from app.models.protocol import ProcessingProtocolRecord, RiskReferenceRecord
from app.services.risk_reference import (ACTIVE_RULE_VERSION, RULE_VERSIONS, ClosingInputs, InvalidClosingInputs, compute,
                                         validated_for)

INPUT_FIELDS = ('average_grade', 'days_scheduled', 'days_attended', 'activities_scheduled', 'activities_delivered',
                'participation_level', 'behavior_incidents')


def rule_for_period(db, period_id) -> str:
    """Regla del periodo: la del protocolo si existe; si no, la regla activa."""
    rule = db.scalar(select(ProcessingProtocolRecord.risk_rule).where(ProcessingProtocolRecord.period_id == period_id))
    version = (rule or {}).get('version', ACTIVE_RULE_VERSION)
    if version not in RULE_VERSIONS:
        raise AppError(409, 'RISK_RULE_UNKNOWN', 'La regla de riesgo del protocolo no es válida.')
    return version


def latest(db, snapshot_id, lock=False, rule_version=ACTIVE_RULE_VERSION):
    query = (select(RiskReferenceRecord).where(RiskReferenceRecord.snapshot_id == snapshot_id,
        RiskReferenceRecord.rule_version == rule_version).order_by(RiskReferenceRecord.revision.desc()).limit(1))
    if lock:
        # La tabla es de solo inserción (sin UPDATE para riesgo_app): se serializa por corte con un bloqueo asesor.
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': f'risk-reference:{snapshot_id}'})
    return db.scalar(query)


def same_evidence(record, closing_date, available_at, inputs: ClosingInputs, bimester) -> bool:
    return (record.closing_date == closing_date and record.closing_available_at == available_at
            and record.bimester == bimester
            and all(getattr(record, field) == getattr(inputs, field) for field in INPUT_FIELDS))


def record_closing(db, actor, snapshot_id: UUID, bimester: str, closing_date: date, closing_available_at: datetime,
                   inputs: ClosingInputs, request_id):
    """Inserta (sin confirmar) la revisión vigente del cierre de un corte con la regla de su periodo. Devuelve (registro, creado)."""
    if actor.role != 'ADMIN':
        raise AppError(403, 'FORBIDDEN', 'Solo ADMIN registra riesgo de referencia.')
    snapshot = db.scalar(select(SnapshotRecord).where(SnapshotRecord.id == snapshot_id))
    if snapshot is None:
        raise AppError(404, 'SNAPSHOT_NOT_FOUND', 'El corte no está disponible.')
    rule = rule_for_period(db, snapshot.period_id)
    try:
        inputs = validated_for(rule, inputs)            # V2: la participación no se lee ni se valida (queda None)
        result = compute(rule, inputs)
    except InvalidClosingInputs as error:
        raise AppError(422, 'INVALID_CLOSING_INPUTS', 'Los insumos de cierre no son válidos (' + str(error) + ').') from None
    prior = latest(db, snapshot_id, lock=True, rule_version=rule)
    if prior is not None and same_evidence(prior, closing_date, closing_available_at, inputs, bimester):
        return prior, False
    row = RiskReferenceRecord(enrollment_id=snapshot.enrollment_id, period_id=snapshot.period_id,
        data_origin=snapshot.data_origin, snapshot_id=snapshot.id, bimester=bimester, rule_version=rule,
        closing_date=closing_date, closing_available_at=closing_available_at,
        points_grade=result.points_grade, points_attendance=result.points_attendance,
        points_activities=result.points_activities, points_participation=result.points_participation,
        points_conduct=result.points_conduct, total_points=result.total_points, risk_level=result.risk_level,
        revision=(prior.revision + 1) if prior else 1, supersedes_id=prior.id if prior else None,
        computed_by=actor.id, **{field: getattr(inputs, field) for field in INPUT_FIELDS})
    db.add(row)
    db.flush()
    db.add(AuditEvent(actor_id=actor.id, entity_type='RISK_REFERENCE', entity_id=row.id, action='RISK_REFERENCE_RECORDED',
        request_id=request_id, recorded_at=datetime.now(UTC),
        payload={'risk_reference_id': str(row.id), 'snapshot_id': str(snapshot.id), 'revision': row.revision}))
    return row, True


def latest_by_snapshot(db, period_id, bimester=None, rule_version=None):
    """Última revisión por corte (snapshot_id → registro) de la regla del periodo, para indicadores y evaluaciones."""
    rule = rule_version or rule_for_period(db, period_id)
    query = (select(RiskReferenceRecord).where(RiskReferenceRecord.period_id == period_id,
        RiskReferenceRecord.rule_version == rule).distinct(RiskReferenceRecord.snapshot_id)
        .order_by(RiskReferenceRecord.snapshot_id, RiskReferenceRecord.revision.desc()))
    if bimester is not None:
        query = query.where(RiskReferenceRecord.bimester == bimester)
    return {row.snapshot_id: row for row in db.scalars(query)}


def references_for_snapshot(db, snapshot_id):
    return list(db.scalars(select(RiskReferenceRecord).where(RiskReferenceRecord.snapshot_id == snapshot_id)
                           .order_by(RiskReferenceRecord.revision)))


@dataclass(frozen=True)
class ClosingRow:
    line: int
    student_code: str
    bimester: str
    closing_date: date
    closing_available_at: datetime
    inputs: ClosingInputs


def resolve_snapshot(db, period_id, student_code, closing_date):
    """Corte del estudiante cuya fecha objetivo es la del cierre (última revisión)."""
    return db.execute(text('''SELECT sn.id FROM risk_school.academic_snapshots sn
        JOIN risk_school.enrollments e ON e.id=sn.enrollment_id JOIN risk_school.students s ON s.id=e.student_id
        WHERE e.period_id=:period AND s.anon_code=:code AND sn.target_date=:closing
        ORDER BY sn.revision DESC,sn.cutoff_at DESC LIMIT 1'''),
        {'period': period_id, 'code': student_code, 'closing': closing_date}).scalar()


def load_closings(db, actor, period_id, rows: list[ClosingRow], request_id):
    """Todo o nada: valida y registra todas las filas en una transacción. Solo códigos en errores."""
    created = reused = 0
    problems = []
    try:
        for item in rows:
            snapshot_id = resolve_snapshot(db, period_id, item.student_code, item.closing_date)
            if snapshot_id is None:
                problems.append({'row': item.line, 'code': 'SNAPSHOT_NOT_FOUND'})
                continue
            try:
                _, was_created = record_closing(db, actor, snapshot_id, item.bimester, item.closing_date,
                                                item.closing_available_at, item.inputs, request_id)
            except AppError as error:
                problems.append({'row': item.line, 'code': error.code})
                continue
            except IntegrityError:
                # La transacción queda abortada: se informa la fila y se detiene la carga completa.
                db.rollback()
                raise AppError(422, 'CLOSING_ROWS_REJECTED', 'Una fila de cierre no cumple las reglas de integridad; no se guardó ninguna.',
                               details=problems + [{'row': item.line, 'code': 'INTEGRITY_CONFLICT'}]) from None
            created += was_created
            reused += not was_created
        if problems:
            raise AppError(422, 'CLOSING_ROWS_REJECTED', 'Hay filas de cierre rechazadas; no se guardó ninguna.', details=problems)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'created': created, 'reused': reused, 'rows': len(rows)}
