"""Base ejecutable de S1; no inicia migraciones ni semillas automáticamente."""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.v1 import auth, catalogs, health
from app.core.config import Settings, get_settings
from app.core.database import Database
from app.core.errors import AppError, error_content
from app.core.rate_limit import LoginLimiter


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        database.engine.dispose()

    application = FastAPI(
        title="Seguimiento Escolar DEMO — S1",
        version="0.1.1",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.settings = settings
    application.state.database = database
    application.state.login_limiter = LoginLimiter(
        settings.login_attempt_limit, settings.login_window_seconds, settings.login_max_keys
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        expose_headers=["X-Request-ID"],
    )

    @application.middleware("http")
    async def response_controls(request: Request, call_next):
        # No confiar en un identificador enviado por el navegador ni registrar cabeceras/cuerpos.
        request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else None
        return JSONResponse(status_code=exc.status_code, content=error_content(request, exc.code, exc.message), headers=headers)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(part) for part in error["loc"][1:]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content=error_content(request, "VALIDATION_ERROR", "Revisa los datos de la solicitud.", details))

    @application.exception_handler(SQLAlchemyError)
    async def database_unavailable(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content=error_content(request, "SERVICE_UNAVAILABLE", "El servicio no está disponible. Inténtalo nuevamente."))

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content=error_content(request, "HTTP_ERROR", "La solicitud no se puede atender."))

    application.include_router(health.router, prefix="/api/v1")
    application.include_router(auth.router, prefix="/api/v1")
    application.include_router(catalogs.router, prefix="/api/v1")
    return application


app = create_app()
