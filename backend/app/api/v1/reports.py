from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Query, Request, Response
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import request_id
from app.schemas.s5 import ReportSummary, EvaluationStatus, AlertStatus
from app.services import reports as service

router=APIRouter(prefix='/reports',tags=['reports'])


@router.get('/summary',response_model=ReportSummary,operation_id='reportSummary')
def summary(request: Request,context: AuthenticatedSession,db: DbSession,period_id: UUID,
        section_id: UUID | None=None,search: str | None=Query(None,max_length=40),
        risk_level: Literal['LOW','MEDIUM','HIGH'] | None=None,
        evaluation_status: EvaluationStatus | None=None,alert_status: AlertStatus | None=None,
        page: int=Query(1,ge=1,le=10000),page_size: int=Query(20,ge=1,le=100)):
    return service.summary(db,context.user,request.app.state.settings,period_id=period_id,
        section_id=section_id,search=search,risk_level=risk_level,evaluation_status=evaluation_status,
        alert_status=alert_status,page=page,page_size=page_size)


@router.get('/export.csv',response_class=Response,operation_id='exportReportCsv',
    responses={200:{'content':{'text/csv':{'schema':{'type':'string','format':'binary'}}}}})
def export(request: Request,context: AuthenticatedSession,db: DbSession,period_id: UUID,
        section_id: UUID | None=None,search: str | None=Query(None,max_length=40),
        risk_level: Literal['LOW','MEDIUM','HIGH'] | None=None,
        evaluation_status: EvaluationStatus | None=None,alert_status: AlertStatus | None=None):
    body=service.export_csv(db,context.user,request.app.state.settings,request_id(request),period_id=period_id,
        section_id=section_id,search=search,risk_level=risk_level,evaluation_status=evaluation_status,
        alert_status=alert_status)
    return Response(content=body,media_type='text/csv; charset=utf-8',headers={
        'Content-Disposition':'attachment; filename="seguimiento-escolar-reporte.csv"',
        'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
