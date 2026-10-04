from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.schemas.s1 import Period, Section
from app.services import catalogs as catalog_service

router = APIRouter(tags=["catalogs"])


@router.get("/periods", response_model=list[Period], operation_id="periods")
def periods(context: AuthenticatedSession, db: DbSession) -> list[Period]:
    return [Period.model_validate(period) for period in catalog_service.periods(db, context.user)]


@router.get("/sections", response_model=list[Section], operation_id="sections")
def sections(context: AuthenticatedSession, db: DbSession, period_id: UUID = Query()) -> list[Section]:
    return [Section.model_validate(section) for section in catalog_service.sections(db, context.user, period_id)]
