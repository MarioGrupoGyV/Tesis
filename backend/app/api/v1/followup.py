from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import AppError, request_id
from app.schemas import s5
from app.services import followup as service
from app.services.auth import check_csrf

router=APIRouter(tags=['followup'])


async def input_payload(request,schema):
    try:
        return schema.model_validate(await request.json())
    except ValidationError as exc:
        details=[{'field':'.'.join(str(part) for part in error['loc']) or 'body',
            'message':error['msg']} for error in exc.errors(include_input=False,include_url=False)]
        raise AppError(422,'VALIDATION_ERROR','Revisa los campos, versiones, límites y fechas con zona horaria de la solicitud.',details=details) from None
    except ValueError:
        raise AppError(422,'VALIDATION_ERROR','Revisa los campos, versiones, límites y fechas con zona horaria de la solicitud.') from None


def write_gate(request,context,csrf_token,db,admin=False):
    (service.require_admin if admin else service.require_writer)(context.user)
    check_csrf(context,csrf_token,request.app.state.settings)
    from app.services.processing_policy import synthetic_studies,require_processing_protocol
    if not synthetic_studies(db):
        require_processing_protocol()


@router.post('/alerts/sync',response_model=s5.FollowupResult,operation_id='syncAlerts')
async def sync(request: Request,context: AuthenticatedSession,db: DbSession,
        csrf_token: str | None=Header(default=None,alias='X-CSRF-Token')):
    write_gate(request,context,csrf_token,db,admin=True)
    payload=await input_payload(request,s5.SyncInput)
    return await run_in_threadpool(service.sync_operation,db,context.user,payload.period_id,
        request.app.state.settings,request_id(request))


@router.get('/alerts',response_model=s5.AlertPage,operation_id='listAlerts')
def alerts(request: Request,context: AuthenticatedSession,db: DbSession,period_id: UUID,
        section_id: UUID | None=None,status: s5.AlertStatus | None=None,
        severity: Literal['MEDIUM','HIGH'] | None=None,search: str | None=Query(None,max_length=40),
        sort: Literal['anon_code','severity_desc','updated_desc']='updated_desc',
        page: int=Query(1,ge=1,le=10000),page_size: int=Query(20,ge=1,le=100)):
    return service.list_alerts(db,context.user,request.app.state.settings,period_id=period_id,
        section_id=section_id,status=status,severity=severity,search=search,sort=sort,page=page,page_size=page_size)


@router.get('/alerts/{id}',response_model=s5.AlertDetail,operation_id='alertDetail')
def alert(id: UUID,request: Request,context: AuthenticatedSession,db: DbSession):
    return service.detail(db,context.user,id,request.app.state.settings)


@router.patch('/alerts/{id}',response_model=s5.AlertDetail,operation_id='updateAlert')
async def patch_alert(id: UUID,request: Request,context: AuthenticatedSession,db: DbSession,
        csrf_token: str | None=Header(default=None,alias='X-CSRF-Token')):
    write_gate(request,context,csrf_token,db)
    payload=await input_payload(request,s5.AlertPatch)
    return await run_in_threadpool(service.patch_alert,db,context.user,id,payload,
        request.app.state.settings,request_id(request))


@router.post('/interventions',response_model=s5.InterventionCreateResult,status_code=201,operation_id='createIntervention')
async def create(request: Request,response: Response,context: AuthenticatedSession,db: DbSession,
        csrf_token: str | None=Header(default=None,alias='X-CSRF-Token')):
    write_gate(request,context,csrf_token,db)
    payload=await input_payload(request,s5.InterventionCreate)
    result=await run_in_threadpool(service.create_intervention,db,context.user,payload,
        request.app.state.settings,request_id(request))
    response.status_code=200 if result.reused_result else 201
    return result


@router.patch('/interventions/{id}',response_model=s5.InterventionView,operation_id='updateIntervention')
async def patch_intervention(id: UUID,request: Request,context: AuthenticatedSession,db: DbSession,
        csrf_token: str | None=Header(default=None,alias='X-CSRF-Token')):
    write_gate(request,context,csrf_token,db)
    payload=await input_payload(request,s5.InterventionPatch)
    return await run_in_threadpool(service.patch_intervention,db,context.user,id,payload,
        request.app.state.settings,request_id(request))
