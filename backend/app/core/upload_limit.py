"""Acota también multipart/chunked antes de que el parser cree archivos temporales."""
from uuid import uuid4
from starlette.responses import JSONResponse
from app.services.csv_validation import MAX_BYTES


class ImportBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST' or scope['path'] != '/api/v1/imports/preview':
            return await self.app(scope, receive, send)
        chunks, length = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            length += len(chunk)
            if length > MAX_BYTES + 64 * 1024:
                response = JSONResponse(status_code=422, content={
                    'code': 'CSV_TOO_LARGE', 'message': 'Reduce el archivo a máximo 5 MiB y los metadatos multipart a 64 KiB.',
                    'details': [{'row': 1, 'field': 'file', 'message': 'Usa un solo archivo de máximo 5 MiB.'}],
                    'request_id': str(scope.get('state', {}).get('request_id') or uuid4()),
                })
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()

        await self.app(scope, bounded_receive, send)
