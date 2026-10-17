from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Header, Query, Request
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import AppError, request_id
from app.schemas.ml import StudentEvaluation
from app.services.auth import check_csrf
from app.schemas.s2 import StudentDetail, StudentPage, TimelineEventPage
from app.services import students as service

router = APIRouter(prefix='/students', tags=['students'])


@router.get('', response_model=StudentPage, operation_id='students')
def students(context: AuthenticatedSession, db: DbSession, period_id: UUID,
             section_id: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             search: str | None = Query(None, max_length=160), risk_level: Literal['LOW', 'MEDIUM', 'HIGH'] | None = None,
             sort: Literal['anon_code', 'risk_desc', 'updated_desc'] = 'anon_code'):
    return service.list_students(db, context.user, period_id=period_id, section_id=section_id, page=page,
        page_size=page_size, search=search, risk_level=risk_level, sort=sort)


@router.get('/{id}', response_model=StudentDetail, operation_id='studentDetail')
def detail(id: UUID, period_id: UUID, context: AuthenticatedSession, db: DbSession):
    return service.detail(db, context.user, id, period_id)


@router.get('/{id}/timeline', response_model=TimelineEventPage, operation_id='studentTimeline')
def timeline(id: UUID, period_id: UUID, context: AuthenticatedSession, db: DbSession,
             page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    return service.timeline(db, context.user, id, period_id, page, page_size)


@router.post('/{id}/evaluate', response_model=StudentEvaluation, operation_id='evaluateStudent')
def evaluate(id: UUID, period_id: UUID, request: Request, context: AuthenticatedSession, db: DbSession,
             token: str | None = Header(None, alias='X-CSRF-Token')):
    from app.services import ml as ml_service
    ml_service.require_admin(context.user)
    check_csrf(context, token, request.app.state.settings)
    if request.headers.get('origin') not in request.app.state.settings.origins:
        raise AppError(403, 'ORIGIN_INVALID', 'El origen de la solicitud no está autorizado.')
    return ml_service.evaluate_student(db, context.user, id, period_id, request.app.state.settings, request_id(request))
