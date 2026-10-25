"""Indicadores de la tesis (Anexo 1) calculados sobre datos del sistema. Solo lectura.

Un único camino de cálculo: filas por estudiante (SQL) → agregación en Python por sección y total.
El riesgo de referencia solo existe hoy en la carga privada del estudio sintético (resultados futuros
vinculados a los cortes CSV importados); sin él los indicadores dependientes se informan como null.
"""
import csv
from datetime import UTC, date, datetime, time, timedelta
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
from types import SimpleNamespace
from app.services import risk_reference_store
from app.services.processing_policy import study_for_period
from app.services.processing_protocol import protocol_confirms_period
from app.services.reports import safe_csv_text
from app.services.simulated_clock import is_retrospective

LIMA = ZoneInfo('America/Lima')
OPPORTUNE_WINDOW_DAYS = 14  # la tesis: «dos semanas» desde la emisión de la alerta
CLASSES = ('LOW', 'MEDIUM', 'HIGH')
NOTICE_REAL = ('Datos reales locales — análisis exploratorio, no demuestra eficacia escolar. Las alertas marcadas como '
               'simulación retrospectiva las generó el modelo ahora sobre cortes pasados: no son alertas emitidas en su momento.')
OOF_LABEL = 'validación cruzada (fuera de muestra)'
IN_SAMPLE_LABEL = 'en memoria, no valida el modelo'
SCOPE = {'SYNTHETIC': 'SYNTHETIC_STUDY', 'REAL': 'INSTITUTIONAL_STUDY'}
NOTICE = ('Indicadores calculados sobre un estudio con datos sintéticos (simulación). No son resultados del colegio '
          'ni miden eficacia escolar.')
CSV_HEADERS = ('origen', 'alcance', 'periodo', 'as_of_utc', 'codigo_anonimo', 'grado', 'seccion', 'elegible',
    'promedio', 'asistencia', 'riesgo_referencia', 'riesgo_predicho', 'fecha_alerta_utc', 'alerta_antes_cierre',
    'nia', 'intervencion_oportuna', 'dias_hasta_intervencion', 'motivo_exclusion', 'fecha_deteccion_utc',
    'simulacion_retrospectiva', 'metric_basis', 'deteccion_validada_pct', 'deteccion_validada_sd_pct', 'deteccion_validada_repeticiones',
    'deteccion_validada_metric_basis')


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
    protocol = None
    if period.data_origin == 'REAL':
        _, protocol = study_for_period(db, period)  # sin protocolo confirmado: INSTITUTIONAL_PROCESSING_NOT_READY
        if user.role == 'RESEARCHER':
            raise AppError(403, 'FORBIDDEN', 'Los indicadores con datos reales no están disponibles para este rol.')
    elif period.data_origin != 'SYNTHETIC':
        raise AppError(422, 'ORIGIN_NOT_SUPPORTED', 'Origen no admitido en este entorno.')
    allowed = sections_for_period(db, period, user.id if user.role == 'TUTOR' else None)
    if user.role == 'TUTOR' and not allowed:
        raise AppError(403, 'FORBIDDEN', 'No tienes secciones asignadas en este periodo.')
    if section_id is not None and section_id not in {s.id for s in allowed}:
        raise AppError(404, 'SECTION_NOT_FOUND', 'La sección no está disponible en este periodo.')
    return period, allowed, protocol


def contexts(db, user):
    """Periodos y secciones que el rol puede consultar en indicadores; no depende del catálogo general."""
    if user.role not in ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'):
        raise AppError(403, 'FORBIDDEN', 'Tu rol no tiene acceso a indicadores.')
    periods = db.scalars(select(AcademicPeriod).join(SyntheticStudyRecord, SyntheticStudyRecord.period_id == AcademicPeriod.id)
        .where(AcademicPeriod.data_origin.in_(('SYNTHETIC', 'REAL'))).order_by(AcademicPeriod.start_date.desc(), AcademicPeriod.id)).all()
    result = []
    for period in periods:
        study = db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id == period.id))
        if period.data_origin == 'REAL' and (user.role == 'RESEARCHER' or not protocol_confirms_period(db, period.id)):
            continue
        allowed = sections_for_period(db, period, user.id if user.role == 'TUTOR' else None)
        if user.role == 'TUTOR' and not allowed:
            continue
        result.append(schemas.IndicatorContext(period_id=period.id, period_code=period.code, school_year=period.school_year,
            is_locked=period.is_locked, data_origin=period.data_origin,
            bimesters=[b['code'] for b in study.config['protocol']['bimesters']] if period.data_origin == 'REAL' else [],
            sections=[schemas.ContextSection(id=s.id, code=s.code, grade=s.grade) for s in allowed]))
    return result


def reference_map(db, settings, period):
    """snapshot_id (BD) → riesgo de referencia, o (None, motivo) si el sistema no lo guarda."""
    if period.data_origin == 'REAL':
        # REAL: referencias de la regla del periodo (su protocolo; RIESGO_V2 en los nuevos) calculadas por el backend con insumos de
        # cierre (risk_references, insert-only).
        found = risk_reference_store.latest_by_snapshot(db, period.id)
        return ({str(key): item.risk_level for key, item in found.items()}, None) if found else (None, 'REFERENCE_NOT_AVAILABLE')
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


def detection_before_close(row, close_at, lead_days):
    """PDER por corte: la PREDICCIÓN de este corte (media/alta) se emitió antes del cierre menos el margen.
    No se hereda la alerta de otro corte: la alerta única de la matrícula solo sirve para NIA e intervención oportuna."""
    instant = row['prediction_instant']
    return bool(row['predicted_risk'] in ('MEDIUM', 'HIGH') and instant is not None and instant < close_at - timedelta(days=lead_days))


def student_records(db, settings, period, allowed_ids, as_of, close_at, window=OPPORTUNE_WINDOW_DAYS, lead_days=0,
                    target_date=None):
    rows = repository.student_rows(db, period.id, as_of, allowed_ids, period.data_origin, target_date)
    references, reference_reason = reference_map(db, settings, period)
    records = []
    for row in rows:
        eligible = bool(row['is_active'] and row['eligible_for_processing'])
        reference = references.get(str(row['snapshot_id'])) if references is not None and row['snapshot_id'] else None
        opened = row['alert_opened_at']
        detected = row['alert_detected_at'] or opened
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
            # PDER: la detección (simulada en retrospectiva) llega antes del cierre; la oportunidad de intervención
            # usa el instante real de la alerta, porque las intervenciones reales ocurren después de ella.
            before_close=detection_before_close(row, close_at, lead_days),
            covered=row['predicted_risk'] == 'LOW' or row['followup_decision'] in ('CREATED', 'UPDATED'),
            retrospective=is_retrospective(detected, opened) if opened else False, detected=detected,
            opportune=(days is not None and days <= window) if opened else None))
    return records, reference_reason


def intervention_records(db, allowed_ids, period, as_of, window=OPPORTUNE_WINDOW_DAYS):
    """Una fila por intervención realizada. Días = diferencia de fechas calendario en Lima desde la apertura de la alerta."""
    records = []
    for row in repository.intervention_rows(db, period.id, as_of, allowed_ids, period.data_origin):
        opened, performed = row['alert_opened_at'], row['performed_at']
        days = (performed.astimezone(LIMA).date() - opened.astimezone(LIMA).date()).days if opened else None
        records.append(dict(row, days=days, opportune=(0 <= days <= window) if days is not None else None))
    return records


def summarize(rows, section=None, reference_reason=None, interventions=(), window=OPPORTUNE_WINDOW_DAYS, no_interventions=False, oof=None,
              detection=None):
    eligible = [r for r in rows if r['eligible']]
    # CRA por corte: predicción baja, o media/alta que el seguimiento dejó reflejada en una alerta (decisión CREATED/UPDATED).
    covered = sum(1 for r in eligible if r['predicted_risk'] is not None and r['covered'])
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
    opportune = schemas.Opportune(**ratio.model_dump(), window_days=window,
        median_days_to_first=float(median(first_days)) if first_days else None,
        students_with_first_intervention=len(first_days))
    linked = [i for i in interventions if i['alert_opened_at'] is not None]
    by_intervention = pct(sum(1 for i in linked if i['opportune']), len(linked), 'NO_INTERVENTIONS_LINKED_TO_ALERT')
    opportune_by_intervention = schemas.OpportuneByIntervention(**by_intervention.model_dump(), window_days=window,
        without_alert=sum(1 for i in interventions if i['alert_opened_at'] is None))
    if no_interventions:
        # REAL sin intervenciones registradas: NIA y oportunidad no se inventan ni se rellenan con ceros.
        reason = 'NO_REAL_INTERVENTIONS'
        nia = schemas.Nia(total=None, students=None, mean=None, median=None, alerted_students=None, mean_alerted=None,
                          median_alerted=None, reason=reason)
        opportune = schemas.Opportune(numerator=None, denominator=None, percent=None, reason=reason, window_days=window)
        opportune_by_intervention = schemas.OpportuneByIntervention(numerator=None, denominator=None, percent=None,
                                                                    reason=reason, window_days=window, without_alert=0)
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
    basis, label, in_sample = ('IN_SAMPLE' if metrics else None), None, None
    if oof is not None:
        # REAL: la cifra principal sale del informe de validación cruzada del modelo activo (solo nivel periodo);
        # el cálculo en memoria se conserva rotulado y nunca es la cifra principal.
        in_sample = metrics
        metrics, metrics_reason = oof if section is None else (None, 'PERIOD_LEVEL_ONLY')
        basis = 'OUT_OF_FOLD' if metrics else 'IN_SAMPLE' if in_sample else None
        label = OOF_LABEL if metrics else IN_SAMPLE_LABEL if in_sample else None
    validated, validated_reason = None, None
    if detection is not None:
        # REAL: la detección validada es del periodo completo; el PDER del sistema (en memoria) se conserva aparte como dato de funcionamiento.
        validated, validated_reason = detection if section is None else (None, 'PERIOD_LEVEL_ONLY')
    exclusions = schemas.Exclusions(ineligible=sum(1 for r in rows if not r['eligible']),
        no_snapshot=sum(1 for r in eligible if r['snapshot_id'] is None),
        no_reference=sum(1 for r in eligible if r['snapshot_id'] is not None and r['reference'] is None),
        reference_reason=reference_reason)
    return schemas.Summary(section_id=section.id if section else None, section_code=section.code if section else None,
        grade=section.grade if section else None, eligible_students=len(eligible), cra=cra, pder=pder, nia=nia,
        opportune=opportune, opportune_by_intervention=opportune_by_intervention, performance=performance, model_metrics=metrics, model_metrics_reason=metrics_reason,
        metric_basis=basis, metric_label=label, in_sample_metrics=in_sample,
        validated_detection=validated, validated_detection_reason=validated_reason, exclusions=exclusions)


def prv(db, user, period, as_of, section_id):
    if user.role == 'TUTOR' or section_id is not None:
        return schemas.Prv(numerator=None, denominator=None, percent=None, reason='PERIOD_LEVEL_ONLY')
    if period.data_origin == 'REAL':
        # El sistema solo ve el CSV ya filtrado por el conversor; la recepción real no tiene procedencia confirmada (decisión 6).
        return schemas.Prv(numerator=None, denominator=None, percent=None, reason='RECEPTION_PROVENANCE_UNCONFIRMED')
    batches, processed, manual = repository.batch_totals(db, period.id, as_of, period.data_origin)
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


def active_comparison(db, period):
    """(modelo REAL activo, informe de comparación de su estudio); (None, {}) si no hay estudio o modelo activo."""
    from app.models.ml import ModelVersion
    study = db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id == period.id))
    model = db.scalar(select(ModelVersion).where(ModelVersion.study_id == study.id, ModelVersion.is_active.is_(True),
                                                 ModelVersion.status == 'APPROVED', ModelVersion.data_origin == 'REAL')) if study else None
    report = ((study.comparison or {}).get('report') or {}) if study else {}
    return model, report


DETECTION_LABEL = 'detección validada: validación cruzada (fuera de muestra)'


def percent_spread(item):
    """Media y desviación de una tasa (0–1) como porcentaje."""
    mean_, sd = item.get('mean'), item.get('sd')
    return schemas.Spread(mean=None if mean_ is None else round(100.0 * mean_, 4), sd=None if sd is None else round(100.0 * sd, 4))


def out_of_fold_detection(db, period, bimester=None):
    """Detección validada del modelo REAL activo (total o de un bimestre), del informe de comparación.

    Devuelve (ValidatedDetection | None, motivo). Sin modelo, sin informe o sin ese dato: null con NO_OUT_OF_SAMPLE_REPORT."""
    model, report = active_comparison(db, period)
    block = ((report.get('algorithms') or {}).get(model.algorithm) or {}).get('detection') if model else None
    scope = None if not block else block.get('total') if bimester is None else (block.get('by_bimester') or {}).get(bimester)
    if not scope:
        return None, 'NO_OUT_OF_SAMPLE_REPORT'
    return schemas.ValidatedDetection(bimester=bimester, repetitions=scope['repetitions'],
        reference_at_risk_per_repetition=scope['reference_at_risk_per_repetition'],
        **{key: percent_spread(scope[key]) for key in ('detection', 'medium_detected', 'high_detected', 'high_as_low', 'low_flagged')},
        pooled=schemas.DetectionCounts(**scope['pooled']), metric_label=DETECTION_LABEL, note=block['note']), None


def out_of_fold_metrics(db, period):
    """Métricas validadas (CV agrupada por estudiante) del informe de comparación del modelo REAL activo.

    Devuelve (ModelMetrics | None, motivo). Sin modelo activo o sin informe: null con NO_OUT_OF_SAMPLE_REPORT."""
    model, report = active_comparison(db, period)
    summary = ((report.get('algorithms') or {}).get(model.algorithm) or {}).get('repeated_cv') if model else None
    if not summary:
        return None, 'NO_OUT_OF_SAMPLE_REPORT'
    per_class = {name: schemas.ClassMetric(support=item['support_per_repetition'], precision=item['precision']['mean'],
                                           recall=item['recall']['mean'], f1=item['f1']['mean']) for name, item in summary['per_class'].items()}
    macro = summary['macro']
    return schemas.ModelMetrics(n=sum(item.support for item in per_class.values()), class_order=summary['class_order'],
        confusion_matrix=summary['aggregated_confusion_matrix'], per_class=per_class,
        macro=schemas.MacroMetrics(**{key: macro[key]['mean'] for key in ('precision', 'recall', 'f1')}),
        accuracy=summary['accuracy']['mean'], not_estimable_reasons={},
        repetitions=summary['repetitions'], macro_sd={key: macro[key]['sd'] for key in ('precision', 'recall', 'f1')}), None


def bimester_of(protocol, code):
    if protocol is None:
        raise AppError(422, 'BIMESTER_NOT_APPLICABLE', 'El filtro por bimestre solo aplica a periodos con protocolo REAL.')
    for item in protocol.bimesters:
        if item['code'] == code:
            return item
    raise AppError(404, 'BIMESTER_NOT_FOUND', 'El bimestre no existe en el protocolo del periodo.')


def compute(db, user, settings, period_id, section_id, as_of, close_at, bimester=None):
    period, allowed, protocol = context(db, user, period_id, section_id)
    as_of = resolve_as_of(as_of)
    chosen = [s for s in allowed if section_id is None or s.id == section_id]
    window, lead, target = OPPORTUNE_WINDOW_DAYS, 0, None
    if protocol is not None:
        windows = protocol.opportune_windows
        window, lead = windows['intervention_days'], windows['detection_days']
    if bimester is not None:
        item = bimester_of(protocol, bimester)
        target = date.fromisoformat(item['close_date']) if isinstance(item['close_date'], str) else item['close_date']
        if close_at is None:
            close_at = datetime.combine(target + timedelta(days=1), time.min, tzinfo=LIMA).astimezone(UTC)
    close = close_instant(period, close_at)
    records, reference_reason = student_records(db, settings, period, [s.id for s in chosen], as_of, close, window, lead, target)
    no_interventions = period.data_origin == 'REAL' and not any(
        r['nia'] for r in records) and not repository.intervention_rows(db, period.id, as_of, [s.id for s in chosen], 'REAL')
    return SimpleNamespace(period=period, allowed=allowed, chosen=chosen, as_of=as_of, close=close, records=records,
        reference_reason=reference_reason, window=window, bimester=bimester, no_interventions=no_interventions,
        oof=out_of_fold_metrics(db, period) if period.data_origin == 'REAL' else None,
        detection=out_of_fold_detection(db, period, bimester) if period.data_origin == 'REAL' else None)


def indicators(db, user, settings, period_id, section_id, as_of, close_at, bimester=None):
    run = compute(db, user, settings, period_id, section_id, as_of, close_at, bimester)
    period = run.period
    events = intervention_records(db, [s.id for s in run.chosen], period, run.as_of, run.window)
    sections = [summarize([r for r in run.records if r['section_id'] == s.id], s, run.reference_reason,
                          [i for i in events if i['section_id'] == s.id], run.window, run.no_interventions, run.oof, run.detection)
                for s in run.chosen]
    real = period.data_origin == 'REAL'
    return schemas.IndicatorsResponse(period_id=period.id, period_code=period.code, data_origin=period.data_origin,
        is_simulation=not real, notice=NOTICE_REAL if real else NOTICE, bimester=run.bimester,
        retrospective_alerts=sum(1 for r in run.records if r['retrospective']),
        as_of=run.as_of, close_at=run.close, opportune_window_days=run.window,
        section_id=section_id, authorized_section_ids=[s.id for s in run.allowed],
        prv=prv(db, user, period, run.as_of, section_id),
        total=summarize(run.records, None, run.reference_reason, events, run.window, run.no_interventions, run.oof, run.detection),
        sections=sections)


def student_item(record):
    risky = record['eligible'] and record['reference'] in ('MEDIUM', 'HIGH')
    return schemas.StudentIndicator(anon_code=record['anon_code'], grade=record['grade'],
        section_code=record['section_code'], eligible=record['eligible'],
        average_grade=float(record['average_grade']) if record['average_grade'] is not None else None,
        attendance_pct=float(record['attendance_pct']) if record['attendance_pct'] is not None else None,
        reference_risk=record['reference'], predicted_risk=record['predicted_risk'],
        alert_opened_at=record['alert_opened_at'], alert_detected_at=record['detected'] if record['alert_opened_at'] else None,
        retrospective=record['retrospective'], alert_before_close=record['before_close'] if risky else None,
        nia=record['nia'], opportune=record['opportune'], days_to_first_intervention=record['days'],
        exclusion_reason=record['exclusion'])


def students(db, user, settings, period_id, section_id, as_of, close_at, page, page_size, bimester=None):
    run = compute(db, user, settings, period_id, section_id, as_of, close_at, bimester)
    items = [student_item(r) for r in run.records[(page - 1) * page_size: page * page_size]]
    return schemas.StudentIndicatorPage(period_id=run.period.id, as_of=run.as_of, items=items, total=len(run.records),
        page=page, page_size=page_size)


def metric_basis(run):
    """Base de las métricas del periodo: validadas fuera de muestra (REAL con informe) o en memoria."""
    return 'OUT_OF_FOLD' if run.oof is not None and run.oof[0] is not None else 'IN_SAMPLE'


def yes_no(value):
    return '' if value is None else 'SI' if value else 'NO'


def export_csv(db, user, settings, request_id, period_id, section_id, as_of, close_at, bimester=None):
    try:
        run = compute(db, user, settings, period_id, section_id, as_of, close_at, bimester)
        period, allowed, as_of, records = run.period, run.allowed, run.as_of, run.records
        content = io.StringIO(newline='')
        writer = csv.writer(content, lineterminator='\r\n', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_HEADERS)
        # Detección validada del periodo (REAL, modelo activo): misma cifra en cada fila, rotulada con su base; vacía si no hay informe.
        validated = run.detection[0] if run.detection else None
        validated_values = (validated.detection.mean, validated.detection.sd, validated.repetitions, validated.metric_basis) if validated else (None,) * 4
        for record in records:
            item = student_item(record)
            values = (period.data_origin, SCOPE[period.data_origin], period.code, as_of.astimezone(UTC).isoformat(), item.anon_code,
                item.grade, item.section_code, 'SI' if item.eligible else 'NO', item.average_grade, item.attendance_pct,
                item.reference_risk, item.predicted_risk,
                item.alert_opened_at.astimezone(UTC).isoformat() if item.alert_opened_at else None,
                yes_no(item.alert_before_close), item.nia, yes_no(item.opportune), item.days_to_first_intervention,
                item.exclusion_reason,
                item.alert_detected_at.astimezone(UTC).isoformat() if item.alert_detected_at else None,
                yes_no(item.retrospective) if item.alert_opened_at else None, metric_basis(run), *validated_values)
            writer.writerow([safe_csv_text(value) for value in values])
        db.add(AuditEvent(id=uuid4(), actor_id=user.id, entity_type='REPORT', entity_id=period.id,
            action='INDICATORS_EXPORT_REQUESTED', request_id=request_id, recorded_at=datetime.now(UTC),
            payload={'scope': SCOPE[period.data_origin], 'data_origin': period.data_origin, 'as_of': as_of.isoformat(),
                     'section_id': str(section_id) if section_id else None, 'enrollment_count': len(records),
                     'authorized_section_ids': [str(s.id) for s in allowed]}))
        db.flush()
        db.commit()
        return b'\xef\xbb\xbf' + content.getvalue().encode('utf-8')
    except Exception:
        db.rollback()
        raise


INTERVENTION_CSV_HEADERS = ('origen', 'alcance', 'periodo', 'as_of_utc', 'codigo_anonimo', 'grado', 'seccion',
    'alerta_vinculada', 'fecha_alerta_utc', 'fecha_intervencion_utc', 'dias_desde_alerta', 'oportuna', 'metric_basis')


def intervention_item(record):
    return schemas.InterventionIndicator(anon_code=record['anon_code'], grade=record['grade'],
        section_code=record['section_code'], alert_opened_at=record['alert_opened_at'], performed_at=record['performed_at'],
        days_since_alert=record['days'], opportune=record['opportune'])


def export_interventions_csv(db, user, settings, request_id, period_id, section_id, as_of):
    try:
        run = compute(db, user, settings, period_id, section_id, as_of, None)
        period, allowed, as_of = run.period, run.allowed, run.as_of
        records = intervention_records(db, [s.id for s in run.chosen], period, as_of, run.window)
        content = io.StringIO(newline='')
        writer = csv.writer(content, lineterminator='\r\n', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(INTERVENTION_CSV_HEADERS)
        for record in records:
            item = intervention_item(record)
            values = (period.data_origin, SCOPE[period.data_origin], period.code, as_of.astimezone(UTC).isoformat(), item.anon_code,
                item.grade, item.section_code, 'SI' if item.alert_opened_at else 'NO',
                item.alert_opened_at.astimezone(UTC).isoformat() if item.alert_opened_at else None,
                item.performed_at.astimezone(UTC).isoformat(), item.days_since_alert, yes_no(item.opportune), metric_basis(run))
            writer.writerow([safe_csv_text(value) for value in values])
        db.add(AuditEvent(id=uuid4(), actor_id=user.id, entity_type='REPORT', entity_id=period.id,
            action='INDICATORS_INTERVENTIONS_EXPORT_REQUESTED', request_id=request_id, recorded_at=datetime.now(UTC),
            payload={'scope': SCOPE[period.data_origin], 'data_origin': period.data_origin, 'as_of': as_of.isoformat(),
                     'section_id': str(section_id) if section_id else None, 'intervention_count': len(records),
                     'authorized_section_ids': [str(s.id) for s in allowed]}))
        db.flush()
        db.commit()
        return b'\xef\xbb\xbf' + content.getvalue().encode('utf-8')
    except Exception:
        db.rollback()
        raise
