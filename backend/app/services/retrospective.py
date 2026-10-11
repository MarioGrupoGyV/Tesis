from datetime import datetime, timezone
import csv
import io
from uuid import uuid4

from app.core.errors import AppError
from app.ml.retrospective import RetrospectiveError
from app.ml.retrospective_runtime import evaluate_reference, partial_reference
from app.repositories.retrospective import RetrospectiveStore
from app.schemas.retrospective import RetrospectiveDetail, RetrospectivePage, RetrospectiveSummary


def require_admin(user):
    if user.role != 'ADMIN':
        raise AppError(403, 'FORBIDDEN', 'La evaluación retrospectiva requiere administración.')


def diagnostic(error):
    code = str(error) if isinstance(error, RetrospectiveError) else 'RETROSPECTIVE_STORAGE_UNAVAILABLE'
    status = 404 if code == 'RETROSPECTIVE_NOT_FOUND' else 503 if 'UNAVAILABLE' in code else 422 if 'TEMPORAL' in code or 'SCALE' in code or 'INSUFFICIENT' in code else 409
    return AppError(status, code, 'No se pudo completar la evaluación retrospectiva. Revisa el registro privado, las escalas y las fechas de disponibilidad.')


def project(record, detail=False):
    schema = RetrospectiveDetail if detail else RetrospectiveSummary
    return schema.model_validate({k: record[k] for k in schema.model_fields})


def history(user, settings, page, page_size):
    require_admin(user)
    if settings.ml_storage_dir is None:
        return RetrospectivePage(available=False, items=[], total=0, page=page, page_size=page_size)
    try:
        store = RetrospectiveStore(settings.ml_storage_dir)
        if not (store.root / 'authorization.json').exists():
            return RetrospectivePage(available=False, items=[], total=0, page=page, page_size=page_size)
        store.package()
        records = store.history()
        return RetrospectivePage(available=True, items=[project(r) for r in records[(page - 1) * page_size:page * page_size]],
                                 total=len(records), page=page, page_size=page_size)
    except (RetrospectiveError, OSError) as error:
        raise diagnostic(error) from None


def detail(user, settings, identifier):
    require_admin(user)
    try:
        store = RetrospectiveStore(settings.ml_storage_dir)
        store.package()
        return project(store.run(identifier), detail=True)
    except (RetrospectiveError, OSError) as error:
        raise diagnostic(error) from None


def run(user, settings, request_id):
    require_admin(user)
    try:
        store = RetrospectiveStore(settings.ml_storage_dir)
        record = evaluate_reference(store.package(), uuid4(), user.id)
        source_audit = store.read('authorization.json').get('source_audit')
        if source_audit:
            record['source_audit'] = source_audit
            record['source_events_verified'] = True
            record['temporal_check'] = 'SOURCE_DECLARED_EVENTS_VERIFIED'
        record['request_id'] = str(request_id)
        record['action'] = 'RETROSPECTIVE_EVALUATED'
        store.save_run(record)
        return project(record, detail=True)
    except (RetrospectiveError, OSError) as error:
        raise diagnostic(error) from None


def partial(user, settings, payload):
    require_admin(user)
    try:
        result = partial_reference(RetrospectiveStore(settings.ml_storage_dir).package(),
            payload.term, payload.values.model_dump(), payload.available_at.model_dump(mode='json'))
        return {k: result[k] for k in ('executed_at', 'scope', 'risk_level', 'alert_proposed',
            'probabilities_calibrated', 'notification_sent', 'intervention_performed',
            'compatibility', 'versions', 'version_warnings')}
    except (RetrospectiveError, OSError) as error:
        raise diagnostic(error) from None


def export(user, settings, identifier):
    record = detail(user, settings, identifier)
    stream = io.StringIO(newline='')
    fields = ['evaluation_id', 'executed_at_utc', 'scope', 'cutoff', 'row_number', 'risk_level',
              'reference_risk', 'correct', 'alert_proposed', 'notification_sent', 'intervention_performed']
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in record.predictions:
        writer.writerow({'evaluation_id': str(record.id), 'executed_at_utc': record.executed_at.isoformat(),
                         'scope': record.scope, 'cutoff': record.cutoffs['B2'],
                         **{k: getattr(row, k) for k in fields[4:]}})
    return '\ufeff' + stream.getvalue()
