from uuid import UUID
from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.api.v1.dependencies import AuthenticatedSession
from app.core.errors import AppError, request_id
from app.schemas.retrospective import (RetrospectiveDetail, RetrospectivePage,
    RetrospectivePartialInput, RetrospectivePartialResult)
from app.services import retrospective as service
from app.services.auth import check_csrf

router = APIRouter(tags=['retrospective'])


@router.get('/retrospective/evaluations', response_model=RetrospectivePage, operation_id='retrospectiveHistory')
def history(request: Request, context: AuthenticatedSession, page: int = Query(1, ge=1, le=10000),
            page_size: int = Query(10, ge=1, le=100)):
    return service.history(context.user, request.app.state.settings, page, page_size)


@router.post('/retrospective/evaluations', response_model=RetrospectiveDetail, operation_id='runRetrospective')
async def run(request: Request, context: AuthenticatedSession,
              csrf_token: str | None = Header(default=None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    check_csrf(context, csrf_token, request.app.state.settings)
    return await run_in_threadpool(service.run, context.user, request.app.state.settings, request_id(request))


@router.get('/retrospective/evaluations/{id}', response_model=RetrospectiveDetail, operation_id='retrospectiveDetail')
def detail(id: UUID, request: Request, context: AuthenticatedSession):
    return service.detail(context.user, request.app.state.settings, id)


@router.get('/retrospective/evaluations/{id}/report.csv', operation_id='exportRetrospectiveCsv')
def report(id: UUID, request: Request, context: AuthenticatedSession):
    return Response(service.export(context.user, request.app.state.settings, id), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="evaluacion-retrospectiva-B2.csv"'})


@router.post('/retrospective/partial-prediction', response_model=RetrospectivePartialResult, operation_id='retrospectivePartialPrediction')
async def partial(request: Request, context: AuthenticatedSession,
                  csrf_token: str | None = Header(default=None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    check_csrf(context, csrf_token, request.app.state.settings)
    try:
        payload = RetrospectivePartialInput.model_validate(await request.json())
    except (ValueError, ValidationError):
        raise AppError(422, 'VALIDATION_ERROR', 'Envía tres valores parciales en sus escalas y tres fechas de disponibilidad con zona horaria.') from None
    return await run_in_threadpool(service.partial, context.user, request.app.state.settings, payload)
