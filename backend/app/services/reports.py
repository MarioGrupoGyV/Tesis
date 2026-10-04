"""Indicadores operativos de simulación y CSV seguro, con la misma consulta base."""
import csv
from datetime import UTC,datetime
import io
import unicodedata
from uuid import uuid4
from app.models.s1 import AuditEvent
from app.repositories import reports as repository
from app.schemas import s5
from app.services.followup import context_period

NOTICE='Estado operativo de un estudio con datos sintéticos. No mide eficacia escolar ni resultados de la tesis.'
CSV_HEADERS=('origen','alcance','periodo','generado_en_utc','codigo_sintetico','grado','seccion',
    'ultimo_corte_utc','estado_evaluacion','riesgo_actual','caso_activo','estado_caso_activo',
    'casos_abiertos','casos_en_revision','casos_concluidos','casos_descartados',
    'actividades_planificadas','actividades_realizadas','actividades_canceladas')


def current_rows(db,user,settings,**filters):
    period,_,allowed=context_period(db,user,filters['period_id'],settings,filters.get('section_id'))
    generated,records=repository.rows(db,user,authorized_section_ids=[section.id for section in allowed],**filters)
    items=[]
    for record in records:
        values={key:record['id'] if key=='student_id' else record[key] for key in s5.ReportRow.model_fields}
        items.append(s5.ReportRow.model_validate(values))
    ids=[s.id for s in allowed if filters.get('section_id') is None or s.id==filters['section_id']]
    return period,ids,generated,items


def percentage(count,denominator):
    return s5.Percentage(count=count,denominator=denominator,
        percentage=100.0*count/denominator if denominator else None,
        reason=None if denominator else 'NO_EVALUATED_ENROLLMENTS')


def summary(db,user,settings,**filters):
    page=filters.pop('page',1);page_size=filters.pop('page_size',20)
    period,allowed,generated,items=current_rows(db,user,settings,**filters)
    evaluated=sum(row.evaluation_status=='EVALUATED' for row in items)
    evaluations=s5.EvaluationCounts(evaluated=evaluated,
        not_evaluated=sum(row.evaluation_status=='NOT_EVALUATED' for row in items),
        insufficient_data=sum(row.evaluation_status=='INSUFFICIENT_DATA' for row in items))
    levels={level:sum(row.evaluation_status=='EVALUATED' and row.risk_level==level for row in items)
        for level in ('LOW','MEDIUM','HIGH')}
    cuts=[row.latest_cutoff_at for row in items if row.latest_cutoff_at is not None]
    return s5.ReportSummary(period_id=period.id,period_code=period.code,
        section_id=filters.get('section_id'),authorized_section_ids=allowed,notice=NOTICE,
        generated_at=generated,cutoff_min=min(cuts) if cuts else None,cutoff_max=max(cuts) if cuts else None,
        total=len(items),evaluations=evaluations,
        risks=s5.RiskCounts(**{level.lower():percentage(count,evaluated) for level,count in levels.items()}),
        cases=s5.CaseCounts(open=sum(r.cases_open for r in items),in_review=sum(r.cases_in_review for r in items),
            resolved=sum(r.cases_resolved for r in items),dismissed=sum(r.cases_dismissed for r in items),
            active_enrollments=sum(r.active_alert_id is not None for r in items)),
        interventions=s5.InterventionCounts(planned=sum(r.interventions_planned for r in items),
            done=sum(r.interventions_done for r in items),cancelled=sum(r.interventions_cancelled for r in items)),
        items=items[(page-1)*page_size:page*page_size],page=page,page_size=page_size)


def safe_csv_text(value):
    """Quoting does not stop spreadsheet formulas: strip controls then neutralize.

    Preserve DB values, ordinary Unicode/quotes/separators. Apostrophe guards any
    dangerous first character after whitespace; BOM/control prefixes cannot hide it.
    """
    if value is None:
        return ''
    cleaned=''.join(character for character in str(value) if unicodedata.category(character) not in ('Cc','Cf','Cs'))
    if cleaned.lstrip().startswith(('=','+','-','@')):
        cleaned="'"+cleaned
    return cleaned


def export_csv(db,user,settings,request_id,**filters):
    try:
        period,allowed,generated,items=current_rows(db,user,settings,**filters)
        content=io.StringIO(newline='')
        writer=csv.writer(content,lineterminator='\r\n',quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_HEADERS)
        for row in items:
            values=('SYNTHETIC','SYNTHETIC_STUDY',period.code,generated.isoformat(),row.anon_code,row.grade,row.section_code,
                row.latest_cutoff_at.isoformat() if row.latest_cutoff_at else None,row.evaluation_status,row.risk_level,
                'SI' if row.active_alert_id else 'NO',row.active_alert_status,row.cases_open,row.cases_in_review,
                row.cases_resolved,row.cases_dismissed,row.interventions_planned,row.interventions_done,row.interventions_cancelled)
            writer.writerow([safe_csv_text(value) for value in values])
        body=b'\xef\xbb\xbf'+content.getvalue().encode('utf-8')
        public_filters={key:str(value) if value is not None else None for key,value in filters.items()}
        db.add(AuditEvent(id=uuid4(),actor_id=user.id,entity_type='REPORT',entity_id=period.id,
            action='REPORT_EXPORT_REQUESTED',request_id=request_id,recorded_at=datetime.now(UTC),payload={
                'scope':'SYNTHETIC_STUDY','data_origin':'SYNTHETIC','filters':public_filters,
                'authorized_section_ids':[str(id) for id in allowed],'generated_at':generated.isoformat(),
                'enrollment_count':len(items)}))
        db.flush();db.commit()
        return body
    except Exception:
        db.rollback();raise
