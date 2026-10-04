from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Query
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.schemas.s2 import StudentDetail, StudentPage, TimelineEventPage
from app.services import students as service

router = APIRouter(prefix='/students', tags=['students'])


@router.get('', response_model=StudentPage, operation_id='students')
def students(context: AuthenticatedSession, db: DbSession, period_id: UUID,
             section_id: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             search: str | None = Query(None, max_length=40), risk_level: Literal['LOW', 'MEDIUM', 'HIGH'] | None = None,
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
