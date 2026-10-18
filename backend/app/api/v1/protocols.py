"""Protocolo REAL: solo ADMIN, sesión + CSRF + Origin. En 3B-1 no habilita ninguna operación REAL."""
from uuid import UUID
from fastapi import APIRouter, Header, Request
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.api.v1.manual import gate
from app.core.errors import request_id
from app.schemas.protocol import Protocol, ProtocolCreate
from app.services import processing_protocol as service

router = APIRouter(prefix='/processing-protocols', tags=['protocols'])


@router.post('', response_model=Protocol, operation_id='createProcessingProtocol')
def create(payload: ProtocolCreate, request: Request, context: AuthenticatedSession, db: DbSession,
           token: str | None = Header(None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    gate(request, context, token)
    return service.create(db, context.user, payload, request_id(request))[0]


@router.get('', response_model=Protocol, operation_id='processingProtocolByPeriod')
def by_period(context: AuthenticatedSession, db: DbSession, period_id: UUID):
    return service.by_period(db, context.user, period_id)


@router.post('/{id}/confirm', response_model=Protocol, operation_id='confirmProcessingProtocol')
def confirm(id: UUID, request: Request, context: AuthenticatedSession, db: DbSession,
            token: str | None = Header(None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    gate(request, context, token)
    return service.set_authorization(db, context.user, id, True, request_id(request))[0]


@router.post('/{id}/revoke', response_model=Protocol, operation_id='revokeProcessingProtocol')
def revoke(id: UUID, request: Request, context: AuthenticatedSession, db: DbSession,
           token: str | None = Header(None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    gate(request, context, token)
    return service.set_authorization(db, context.user, id, False, request_id(request))[0]
