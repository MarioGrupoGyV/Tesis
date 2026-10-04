from uuid import UUID
from fastapi import APIRouter, Header, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import AppError, request_id
from app.schemas.s2 import CommitInput, ImportBatch, ImportCommit
from app.services.auth import check_csrf
from app.services import imports as service
from app.services.csv_validation import MAX_BYTES, file_error

router = APIRouter(prefix='/imports', tags=['imports'])


@router.post('/preview', response_model=ImportBatch, status_code=201, operation_id='previewImport')
async def preview(request: Request, response: Response, context: AuthenticatedSession, db: DbSession,
                  csrf_token: str | None = Header(default=None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    settings = request.app.state.settings
    check_csrf(context, csrf_token, settings)
    try:
        async with request.form(max_files=1, max_fields=1, max_part_size=MAX_BYTES) as form:
            if set(form) != {'file', 'period_id'} or any(len(form.getlist(k)) != 1 for k in form):
                raise file_error('INVALID_FORM', 'Envía solo file y period_id, una vez cada uno.')
            upload = form['file']
            if not isinstance(upload, UploadFile):
                raise file_error('INVALID_FORM', 'Envía un archivo CSV en file.')
            try:
                period_id = UUID(str(form['period_id']))
            except ValueError:
                raise file_error('INVALID_PERIOD', 'Usa el UUID del periodo seleccionado.', field='period_id') from None
            content = await upload.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise file_error('CSV_TOO_LARGE', 'Reduce el archivo a un máximo de 5 MiB.')
            result, created = await run_in_threadpool(service.preview, db, context.user, settings,
                period_id, content, upload.filename, request_id(request))
    except HTTPException as exc:
        if exc.status_code == 400:
            raise file_error('INVALID_MULTIPART', 'Envía un solo archivo CSV y un solo period_id en multipart válido.') from None
        raise
    response.status_code = 201 if created else 200
    return result


@router.get('/{id}', response_model=ImportBatch, operation_id='importDetail')
def detail(id: UUID, context: AuthenticatedSession, db: DbSession):
    return ImportBatch.model_validate(service.get_batch(db, context.user, id))


@router.post('/{id}/commit', response_model=ImportCommit, operation_id='commitImport')
def commit(id: UUID, payload: CommitInput, request: Request, context: AuthenticatedSession, db: DbSession,
           csrf_token: str | None = Header(default=None, alias='X-CSRF-Token')):
    service.require_admin(context.user)
    check_csrf(context, csrf_token, request.app.state.settings)
    return service.commit(db, context.user, request.app.state.settings, id, payload.expected_preview_version, request_id(request))
