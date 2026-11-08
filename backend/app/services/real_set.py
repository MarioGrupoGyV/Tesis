"""Conjunto real (ADR 015): solo lectura. No escribe, no evalúa y no expone nombres."""
from collections import Counter
from app.core.errors import AppError
from app.models.s1 import AcademicPeriod
from app.repositories import real_set as repository
from app.schemas import real_set as schemas
from app.services.students import authorize_period


def number(value):
    return float(value) if value is not None else None


def page(db, user, period_id, section_id, page_number, page_size):
    period = db.get(AcademicPeriod, period_id)
    # Un periodo que no es REAL responde igual que uno inexistente: esta vista es solo del conjunto real.
    if period is None or period.data_origin != 'REAL':
        raise AppError(404, 'PERIOD_NOT_FOUND', 'El periodo solicitado no existe.')
    authorize_period(db, user, period_id, section_id)
    students, order = {}, []
    for row in repository.rows(db, user, period_id, section_id):
        item = students.get(row['enrollment_id'])
        if item is None:
            item = students[row['enrollment_id']] = dict(student_id=row['student_id'], anon_code=row['anon_code'], grade=row['grade'],
                                                         section_code=row['section_code'], alert_status=row['alert_status'], cuts=[])
            order.append(item)
        if row['bimester'] is not None:
            item['cuts'].append(schemas.RealSetCut(bimester=row['bimester'], cutoff_at=row['cutoff_at'],
                average_grade=number(row['average_grade']), attendance_pct=number(row['attendance_pct']),
                activities_pct=number(row['activities_pct']), behavior_incidents=row['behavior_incidents'],
                predicted_risk=row['predicted_risk'], reference_risk=row['reference_risk'], reference_points=row['reference_points']))
    cuts = [cut for item in order for cut in item['cuts']]
    bimesters = sorted({cut.bimester for cut in cuts})
    summary = []
    for bimester in bimesters:
        scope = [cut for cut in cuts if cut.bimester == bimester]
        predicted, reference = Counter(cut.predicted_risk for cut in scope), Counter(cut.reference_risk for cut in scope)
        summary.append(schemas.RealSetLevels(bimester=bimester, cuts=len(scope), predicted_low=predicted['LOW'],
            predicted_medium=predicted['MEDIUM'], predicted_high=predicted['HIGH'], predicted_missing=predicted[None],
            reference_low=reference['LOW'], reference_medium=reference['MEDIUM'], reference_high=reference['HIGH']))
    start = (page_number - 1) * page_size
    return schemas.RealSetPage(period_id=period.id, period_code=period.code, is_locked=period.is_locked,
        model_algorithm=repository.active_algorithm(db), bimesters=bimesters, summary=summary, students=len(order),
        alerts=sum(1 for item in order if item['alert_status'] is not None),
        items=[schemas.RealSetStudent(**item) for item in order[start:start + page_size]], total=len(order),
        page=page_number, page_size=page_size)
