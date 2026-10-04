from fastapi import APIRouter, Request
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.schemas.processing import ProcessingStatus
from app.services.processing_policy import processing_status

router = APIRouter(prefix='/processing',tags=['processing'])


@router.get('/status',response_model=ProcessingStatus,operation_id='processingStatus')
def status(request: Request,context: AuthenticatedSession,db: DbSession):
    return processing_status(db,context.user,request.app.state.settings)
