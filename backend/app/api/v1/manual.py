"""M1: sesión + CSRF + Origin; API usa exclusivamente riesgo_app."""
from uuid import UUID
from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import select
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import AppError, request_id
from app.models.s1 import AppUser
from app.repositories import manual as repository
from app.schemas import manual as schema
from app.schemas.s1 import Period, Section, User
from app.schemas.s2 import Snapshot
from app.services import manual as service
from app.services.auth import check_csrf

router=APIRouter(tags=['manual'])


def gate(request,context,token):
    check_csrf(context,token,request.app.state.settings)
    if request.headers.get('origin') not in request.app.state.settings.origins:
        raise AppError(403,'ORIGIN_INVALID','El origen de la solicitud no está autorizado.')


@router.get('/catalogs/tutors',response_model=list[User],operation_id='activeTutors')
def tutors(context:AuthenticatedSession,db:DbSession):
    service.require_admin(context.user)
    return db.scalars(select(AppUser).where(AppUser.role=='TUTOR',AppUser.is_active).order_by(AppUser.display_name)).all()


@router.post('/periods',response_model=Period,operation_id='createPeriod')
def period_create(payload:schema.PeriodCreate,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.catalog_command(db,context.user,payload,None,'period',request_id(request))


@router.patch('/periods/{id}',response_model=Period,operation_id='updatePeriod')
def period_patch(id:UUID,payload:schema.PeriodPatch,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.catalog_command(db,context.user,payload,id,'period',request_id(request))


@router.post('/sections',response_model=Section,operation_id='createSection')
def section_create(payload:schema.SectionCreate,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.catalog_command(db,context.user,payload,None,'section',request_id(request))


@router.patch('/sections/{id}',response_model=Section,operation_id='updateSection')
def section_patch(id:UUID,payload:schema.SectionPatch,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.catalog_command(db,context.user,payload,id,'section',request_id(request))


@router.get('/student-identities',response_model=list[schema.Identity],operation_id='studentIdentities')
def identities(context:AuthenticatedSession,db:DbSession,search:str=Query(min_length=2,max_length=160)):
    service.require_admin(context.user)
    return repository.identities(db,search)


@router.post('/students',response_model=schema.Identity,operation_id='createStudent')
def student_create(payload:schema.StudentCreate,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.create_student(db,context.user,payload,request_id(request))


@router.patch('/students/{id}',response_model=schema.Identity,operation_id='updateStudent')
def student_patch(id:UUID,payload:schema.StudentPatch,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.patch_student(db,context.user,id,payload,request_id(request))


@router.post('/enrollments',response_model=schema.EnrollmentView,operation_id='createEnrollment')
def enrollment_create(payload:schema.EnrollmentCreate,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.enroll(db,context.user,payload,request_id(request))


@router.patch('/enrollments/{id}',response_model=schema.EnrollmentView,operation_id='updateEnrollment')
def enrollment_patch(id:UUID,payload:schema.EnrollmentPatch,request:Request,context:AuthenticatedSession,db:DbSession,
        token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.patch_enrollment(db,context.user,id,payload,request_id(request))


@router.get('/students/{id}/measurements',response_model=schema.MeasurementPage,operation_id='studentMeasurements')
def measurements(id:UUID,period_id:UUID,context:AuthenticatedSession,db:DbSession,
        page:int=Query(1,ge=1,le=10000),page_size:int=Query(10,ge=1,le=100)):
    return service.measurement_page(db,context.user,id,period_id,page,page_size)


@router.post('/students/{id}/measurements',response_model=Snapshot,operation_id='createMeasurement')
def measurement_create(id:UUID,period_id:UUID,payload:schema.MeasurementCreate,request:Request,
        context:AuthenticatedSession,db:DbSession,token:str|None=Header(None,alias='X-CSRF-Token')):
    gate(request,context,token)
    return service.create_measurement(db,context.user,id,period_id,payload,request_id(request))
