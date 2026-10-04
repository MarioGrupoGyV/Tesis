from fastapi import APIRouter, Header, Request, Response

from app.api.v1.dependencies import AuthenticatedSession, DbSession
from app.core.errors import AppError, request_id
from app.core.security import digest_token
from app.schemas.s1 import Csrf, LoginInput, LoginResult, User
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResult, operation_id="login")
def login(payload: LoginInput, request: Request, response: Response, db: DbSession) -> LoginResult:
    settings = request.app.state.settings
    if request.headers.get("origin") not in settings.origins:
        raise AppError(403, "ORIGIN_NOT_ALLOWED", "El origen de la solicitud no está permitido.")
    client_host = request.client.host if request.client else "unknown"
    request.app.state.login_limiter.consume(["ip:" + digest_token(client_host), "email:" + digest_token(str(payload.email).lower())])
    context = auth_service.login(
        db,
        email=str(payload.email),
        password=payload.password,
        settings=settings,
        request_id=request_id(request),
        previous_token=request.cookies.get("session"),
    )
    response.set_cookie(
        "session",
        context.raw_token,
        max_age=settings.session_ttl_seconds,
        expires=context.session.expires_at,
        path="/",
        secure=settings.session_cookie_secure or request.url.scheme == "https",
        httponly=True,
        samesite="lax",
    )
    return LoginResult(
        user=User.model_validate(context.user),
        csrf_token=auth_service.session_csrf(context, settings),
        expires_at=context.session.expires_at,
    )


@router.get("/me", response_model=User, operation_id="me")
def me(context: AuthenticatedSession) -> User:
    return User.model_validate(context.user)


@router.get("/csrf", response_model=Csrf, operation_id="csrf")
def csrf(request: Request, context: AuthenticatedSession) -> Csrf:
    return Csrf(csrf_token=auth_service.session_csrf(context, request.app.state.settings))


@router.post("/logout", status_code=204, operation_id="logout")
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    context: AuthenticatedSession,
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    settings = request.app.state.settings
    auth_service.check_csrf(context, csrf_token, settings)
    auth_service.logout(db, context, request_id(request))
    response.delete_cookie(
        "session",
        path="/",
        secure=settings.session_cookie_secure or request.url.scheme == "https",
        httponly=True,
        samesite="lax",
    )
