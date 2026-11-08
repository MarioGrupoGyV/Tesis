from uuid import UUID
from fastapi import APIRouter, Query
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.schemas.real_set import RealSetPage
from app.services import real_set as service

router = APIRouter(prefix='/real-set', tags=['real-set'])


@router.get('', response_model=RealSetPage, operation_id='realSet')
def real_set(context: AuthenticatedSession, db: DbSession, period_id: UUID, section_id: UUID | None = None,
             page: int = Query(1, ge=1, le=10000), page_size: int = Query(100, ge=1, le=100)):
    return service.page(db, context.user, period_id, section_id, page, page_size)
