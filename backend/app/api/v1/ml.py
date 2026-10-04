from uuid import UUID
from fastapi import APIRouter, Header, Query, Request
from pydantic import ValidationError
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import AppError, request_id
from app.schemas.ml import Model, ModelPage, PredictionRunInput, PredictionRunResult
from app.schemas.s2 import Prediction
from app.services import ml as service
from app.services.auth import check_csrf

router = APIRouter(tags=['ml'])


@router.get('/models',response_model=ModelPage,operation_id='listModels')
def models(context: AuthenticatedSession,db: DbSession,page: int=Query(1,ge=1,le=10000),page_size: int=Query(25,ge=1,le=100)):
    return service.list_models(db,context.user,page,page_size)


@router.get('/models/{id}',response_model=Model,operation_id='modelDetail')
def model(id: UUID,context: AuthenticatedSession,db: DbSession):
    return service.model_detail(db,context.user,id)


@router.post('/predictions/run',response_model=PredictionRunResult,operation_id='runPredictions')
async def run(request: Request,context: AuthenticatedSession,db: DbSession,
              csrf_token: str | None=Header(default=None,alias='X-CSRF-Token')):
    service.require_admin(context.user)
    check_csrf(context,csrf_token,request.app.state.settings)
    # Precedencia explícita antes de parsear datos institucionales o consultar cortes.
    from app.services.processing_policy import synthetic_studies
    if not synthetic_studies(db):
        service.require_ml_protocol()
    try:
        payload = PredictionRunInput.model_validate(await request.json())
    except (ValidationError,ValueError):
        raise AppError(422,'VALIDATION_ERROR','Envía period_id y as_of con zona horaria.') from None
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(service.run_period,db,context.user,payload,request.app.state.settings,request_id(request))


@router.get('/predictions/{id}',response_model=Prediction,operation_id='predictionDetail')
def prediction(id: UUID,context: AuthenticatedSession,db: DbSession):
    return service.prediction_detail(db,context.user,id)
