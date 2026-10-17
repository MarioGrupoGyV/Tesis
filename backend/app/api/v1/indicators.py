from uuid import UUID
from fastapi import APIRouter, Query, Request, Response
from pydantic import AwareDatetime
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import request_id
from app.schemas.indicators import IndicatorContext, IndicatorsResponse, StudentIndicatorPage
from app.services import indicators as service

router = APIRouter(prefix='/indicators', tags=['indicators'])


@router.get('/contexts', response_model=list[IndicatorContext], operation_id='indicatorContexts')
def contexts(context: AuthenticatedSession, db: DbSession):
    return service.contexts(db, context.user)


@router.get('', response_model=IndicatorsResponse, operation_id='indicators')
def indicators(request: Request, context: AuthenticatedSession, db: DbSession, period_id: UUID,
               section_id: UUID | None = None, as_of: AwareDatetime | None = None, close_at: AwareDatetime | None = None):
    return service.indicators(db, context.user, request.app.state.settings, period_id, section_id, as_of, close_at)


@router.get('/students', response_model=StudentIndicatorPage, operation_id='indicatorStudents')
def students(request: Request, context: AuthenticatedSession, db: DbSession, period_id: UUID,
             section_id: UUID | None = None, as_of: AwareDatetime | None = None, close_at: AwareDatetime | None = None,
             page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=100)):
    return service.students(db, context.user, request.app.state.settings, period_id, section_id, as_of, close_at,
                            page, page_size)


@router.get('/export.csv', response_class=Response, operation_id='exportIndicatorsCsv',
            responses={200: {'content': {'text/csv': {'schema': {'type': 'string', 'format': 'binary'}}}}})
def export(request: Request, context: AuthenticatedSession, db: DbSession, period_id: UUID,
           section_id: UUID | None = None, as_of: AwareDatetime | None = None, close_at: AwareDatetime | None = None):
    body = service.export_csv(db, context.user, request.app.state.settings, request_id(request), period_id,
                              section_id, as_of, close_at)
    return Response(content=body, media_type='text/csv; charset=utf-8', headers={
        'Content-Disposition': 'attachment; filename="seguimiento-escolar-indicadores.csv"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
