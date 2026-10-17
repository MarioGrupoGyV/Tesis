"""Indicadores de la tesis (Anexo 1) calculados sobre datos del sistema. Solo lectura.

Un único camino de cálculo: filas por estudiante (SQL) → agregación en Python por sección y total.
El riesgo de referencia solo existe hoy en la carga privada del estudio sintético (resultados futuros
vinculados a los cortes CSV importados); sin él los indicadores dependientes se informan como null.
"""
import csv
from datetime import UTC, datetime, time, timedelta
import io
from statistics import mean, median, stdev
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.errors import AppError
from app.models.s1 import AcademicPeriod, AuditEvent
from app.models.synthetic import SyntheticStudyRecord
from app.repositories import indicators as repository
from app.repositories.s1 import sections_for_period
from app.schemas import indicators as schemas
from app.services.processing_policy import require_processing_protocol
from app.services.reports import safe_csv_text

LIMA = ZoneInfo('America/Lima')
OPPORTUNE_WINDOW_DAYS = 14  # la tesis: «dos semanas» desde la emisión de la alerta
CLASSES = ('LOW', 'MEDIUM', 'HIGH')
NOTICE = ('Indicadores calculados sobre un estudio con datos sintéticos (simulación). No son resultados del colegio '
          'ni miden eficacia escolar.')
CSV_HEADERS = ('origen', 'alcance', 'periodo', 'as_of_utc', 'codigo_anonimo', 'grado', 'seccion', 'elegible',
    'promedio', 'asistencia', 'riesgo_referencia', 'riesgo_predicho', 'fecha_alerta_utc', 'alerta_antes_cierre',
    'nia', 'intervencion_oportuna', 'dias_hasta_intervencion', 'motivo_exclusion')


def pct(numerator, denominator, reason='NO_DENOMINATOR'):
    if not denominator:
        return schemas.Ratio(numerator=numerator, denominator=denominator, percent=None, reason=reason)
    return schemas.Ratio(numerator=numerator, denominator=denominator, percent=round(100.0 * numerator / denominator, 4))


def describe(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return schemas.Descriptive(n=0, mean=None, sd=None, median=None, minimum=None, maximum=None)
    return schemas.Descriptive(n=len(values), mean=round(mean(values), 4),
        sd=round(stdev(values), 4) if len(values) > 1 else None, median=round(median(values), 4),
        minimum=min(values), maximum=max(values))


def context(db, user, period_id, section_id):
    if user.role not in ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'):
        raise AppError(403, 'FORBIDDEN', 'Tu rol no tiene acceso a indicadores.')
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise AppError(404, 'PERIOD_NOT_FOUND', 'El periodo no está disponible.')
    if period.data_origin != 'SYNTHETIC':
        require_processing_protocol()
    allowed = sections_for_period(db, period, user.id if user.role == 'TUTOR' else None)
    if user.role == 'TUTOR' and not allowed:
        raise AppError(403, 'FORBIDDEN', 'No tienes secciones asignadas en este periodo.')
    if section_id is not None and section_id not in {s.id for s in allowed}:
        raise AppError(404, 'SECTION_NOT_FOUND', 'La sección no está disponible en este periodo.')
    return period, allowed


def reference_map(db, settings, period):
    """snapshot_id (BD) → riesgo de referencia, o (None, motivo) si el sistema no lo guarda."""
    study = db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id == period.id,
                                                          SyntheticStudyRecord.data_origin == 'SYNTHETIC'))
    if study is None or not study.bindings:
        return None, 'REFERENCE_NOT_AVAILABLE'
    from app.services.synthetic_study import validate_registered
    try:
        _, payload, _ = validate_registered(db, settings, study)
    except AppError:
        return None, 'STUDY_INTEGRITY_ERROR'
    except OSError:
        return None, 'STUDY_STORAGE_UNAVAILABLE'
    risk_by_generated = {o['snapshot_id']: o['risk'] for o in payload['labels']['outcomes']}
    return {b['snapshot_id']: risk_by_generated.get(b['generated_snapshot_id']) for b in study.bindings}, None


def close_instant(period, close_at):
    if close_at is not None:
        return close_at
    # Cierre del periodo: inicio del día siguiente al último día, en America/Lima.
    return datetime.combine(period.end_date + timedelta(days=1), time.min, tzinfo=LIMA).astimezone(UTC)


def student_records(db, settings, period, allowed_ids, as_of, close_at):
    rows = repository.student_rows(db, period.id, as_of, allowed_ids)
    references, reference_reason = reference_map(db, settings, period)
    records = []
    for row in rows:
        eligible = bool(row['is_active'] and row['eligible_for_processing'])
        reference = references.get(str(row['snapshot_id'])) if references is not None and row['snapshot_id'] else None
        opened = row['alert_opened_at']
        first_done = row['first_done_after_alert']
        days = (first_done.astimezone(LIMA).date() - opened.astimezone(LIMA).date()).days if opened and first_done else None
        reason = None
        if not eligible:
            reason = 'NOT_ELIGIBLE'
        elif row['snapshot_id'] is None:
            reason = 'NO_SNAPSHOT'
        elif reference is None:
            reason = reference_reason or 'NO_REFERENCE_FOR_LATEST_SNAPSHOT'
        records.append(dict(row, eligible=eligible, reference=reference, days=days, exclusion=reason,
            before_close=(opened < close_at) if opened else False,
            opportune=(days is not None and days <= OPPORTUNE_WINDOW_DAYS) if opened else None))
    return records, reference_reason


def summarize(rows, section=None, reference_reason=None):
    eligible = [r for r in rows if r['eligible']]
    covered = sum(1 for r in eligible if r['predicted_risk'] is not None and
                  (r['predicted_risk'] == 'LOW' or r['alert_id'] is not None))
    cra = pct(covered, len(eligible), 'NO_ELIGIBLE_STUDENTS')
    risky_reference = [r for r in eligible if r['reference'] in ('MEDIUM', 'HIGH')]
    no_reference_source = reference_reason and not any(r['reference'] for r in eligible)
    if no_reference_source:
        pder = schemas.Ratio(numerator=None, denominator=None, percent=None, reason=reference_reason)
    else:
        pder = pct(sum(1 for r in risky_reference if r['before_close']), len(risky_reference), 'NO_REFERENCE_MEDIUM_OR_HIGH')
    counts = [r['nia'] for r in eligible]
    alerted = [r['nia'] for r in eligible if r['alert_id'] is not None]
    nia = schemas.Nia(total=sum(counts), students=len(counts), mean=round(mean(counts), 4) if counts else None,
        median=float(median(counts)) if counts else None, alerted_students=len(alerted),
        mean_alerted=round(mean(alerted), 4) if alerted else None,
        median_alerted=float(median(alerted)) if alerted else None, reason=None if counts else 'NO_ELIGIBLE_STUDENTS')
    with_alert = [r for r in eligible if r['alert_id'] is not None]
    ratio = pct(sum(1 for r in with_alert if r['opportune']), len(with_alert), 'NO_ALERTS')
    first_days = [r['days'] for r in with_alert if r['days'] is not None]
    opportune = schemas.Opportune(**ratio.model_dump(), window_days=OPPORTUNE_WINDOW_DAYS,
        median_days_to_first=float(median(first_days)) if first_days else None,
        students_with_first_intervention=len(first_days))
    performance = schemas.Performance(average_grade=describe(r['average_grade'] for r in eligible),
        attendance_pct=describe(r['attendance_pct'] for r in eligible))
    pairs = [(r['reference'], r['predicted_risk']) for r in eligible if r['reference'] and r['predicted_risk']]
    metrics, metrics_reason = None, None
    if no_reference_source:
        metrics_reason = reference_reason
    elif not pairs:
        metrics_reason = 'NO_EVALUATED_STUDENTS_WITH_REFERENCE'
    else:
        from app.ml.evaluate import metrics as compute  # núcleo ML existente; no se duplica
        value = compute([CLASSES.index(a) for a, _ in pairs], [CLASSES.index(b) for _, b in pairs])
        metrics = schemas.ModelMetrics(n=len(pairs), class_order=value['class_order'],
            confusion_matrix=value['confusion_matrix'],
            per_class={k: schemas.ClassMetric(**v) for k, v in value['per_class'].items()},
            macro=schemas.MacroMetrics(**value['macro']), accuracy=value['accuracy'],
            not_estimable_reasons=value['not_estimable_reasons'])
    exclusions = schemas.Exclusions(ineligible=sum(1 for r in rows if not r['eligible']),
        no_snapshot=sum(1 for r in eligible if r['snapshot_id'] is None),
        no_reference=sum(1 for r in eligible if r['snapshot_id'] is not None and r['reference'] is None),
        reference_reason=reference_reason)
    return schemas.Summary(section_id=section.id if section else None, section_code=section.code if section else None,
        grade=section.grade if section else None, eligible_students=len(eligible), cra=cra, pder=pder, nia=nia,
        opportune=opportune, performance=performance, model_metrics=metrics, model_metrics_reason=metrics_reason,
        exclusions=exclusions)


def prv(db, user, period, as_of, section_id):
    if user.role == 'TUTOR' or section_id is not None:
        return schemas.Prv(numerator=None, denominator=None, percent=None, reason='PERIOD_LEVEL_ONLY')
    batches, processed, manual = repository.batch_totals(db, period.id, as_of)
    received, valid_processed = int(batches['received']), int(processed['eligible'])
    ratio = pct(valid_processed, received, 'NO_RECEIVED_RECORDS')
    return schemas.Prv(**ratio.model_dump(), received=received, valid_processed=valid_processed,
        rejected=int(batches['rejected']), valid_not_committed=int(batches['valid_not_committed']),
        ineligible_omitted=int(processed['ineligible']), manual_measurements=int(manual))


def resolve_as_of(as_of):
    now = datetime.now(UTC)
    if as_of is None:
        return now
    if as_of > now:
        raise AppError(422, 'AS_OF_IN_FUTURE', 'as_of no puede estar en el futuro.')
    return as_of


def compute(db, user, settings, period_id, section_id, as_of, close_at):
    period, allowed = context(db, user, period_id, section_id)
    as_of = resolve_as_of(as_of)
    chosen = [s for s in allowed if section_id is None or s.id == section_id]
    close = close_instant(period, close_at)
    records, reference_reason = student_records(db, settings, period, [s.id for s in chosen], as_of, close)
    return period, allowed, chosen, as_of, close, records, reference_reason


def indicators(db, user, settings, period_id, section_id, as_of, close_at):
    period, allowed, chosen, as_of, close, records, reference_reason = compute(
        db, user, settings, period_id, section_id, as_of, close_at)
    sections = [summarize([r for r in records if r['section_id'] == s.id], s, reference_reason) for s in chosen]
    return schemas.IndicatorsResponse(period_id=period.id, period_code=period.code, data_origin='SYNTHETIC',
        is_simulation=True, notice=NOTICE, as_of=as_of, close_at=close, opportune_window_days=OPPORTUNE_WINDOW_DAYS,
        section_id=section_id, authorized_section_ids=[s.id for s in allowed],
        prv=prv(db, user, period, as_of, section_id), total=summarize(records, None, reference_reason), sections=sections)


def student_item(record):
    risky = record['eligible'] and record['reference'] in ('MEDIUM', 'HIGH')
    return schemas.StudentIndicator(anon_code=record['anon_code'], grade=record['grade'],
        section_code=record['section_code'], eligible=record['eligible'],
        average_grade=float(record['average_grade']) if record['average_grade'] is not None else None,
        attendance_pct=float(record['attendance_pct']) if record['attendance_pct'] is not None else None,
        reference_risk=record['reference'], predicted_risk=record['predicted_risk'],
        alert_opened_at=record['alert_opened_at'], alert_before_close=record['before_close'] if risky else None,
        nia=record['nia'], opportune=record['opportune'], days_to_first_intervention=record['days'],
        exclusion_reason=record['exclusion'])


def students(db, user, settings, period_id, section_id, as_of, close_at, page, page_size):
    period, _, _, as_of, _, records, _ = compute(db, user, settings, period_id, section_id, as_of, close_at)
    items = [student_item(r) for r in records[(page - 1) * page_size: page * page_size]]
    return schemas.StudentIndicatorPage(period_id=period.id, as_of=as_of, items=items, total=len(records),
        page=page, page_size=page_size)


def yes_no(value):
    return '' if value is None else 'SI' if value else 'NO'


def export_csv(db, user, settings, request_id, period_id, section_id, as_of, close_at):
    try:
        period, allowed, _, as_of, _, records, _ = compute(db, user, settings, period_id, section_id, as_of, close_at)
        content = io.StringIO(newline='')
        writer = csv.writer(content, lineterminator='\r\n', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_HEADERS)
        for record in records:
            item = student_item(record)
            values = ('SYNTHETIC', 'SYNTHETIC_STUDY', period.code, as_of.astimezone(UTC).isoformat(), item.anon_code,
                item.grade, item.section_code, 'SI' if item.eligible else 'NO', item.average_grade, item.attendance_pct,
                item.reference_risk, item.predicted_risk,
                item.alert_opened_at.astimezone(UTC).isoformat() if item.alert_opened_at else None,
                yes_no(item.alert_before_close), item.nia, yes_no(item.opportune), item.days_to_first_intervention,
                item.exclusion_reason)
            writer.writerow([safe_csv_text(value) for value in values])
        db.add(AuditEvent(id=uuid4(), actor_id=user.id, entity_type='REPORT', entity_id=period.id,
            action='INDICATORS_EXPORT_REQUESTED', request_id=request_id, recorded_at=datetime.now(UTC),
            payload={'scope': 'SYNTHETIC_STUDY', 'data_origin': 'SYNTHETIC', 'as_of': as_of.isoformat(),
                     'section_id': str(section_id) if section_id else None, 'enrollment_count': len(records),
                     'authorized_section_ids': [str(s.id) for s in allowed]}))
        db.flush()
        db.commit()
        return b'\xef\xbb\xbf' + content.getvalue().encode('utf-8')
    except Exception:
        db.rollback()
        raise
