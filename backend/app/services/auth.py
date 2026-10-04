import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import csrf_token_for_session, digest_token, new_session_token, password_verify
from app.models.s1 import AppUser, AuditEvent, UserSession
from app.repositories.s1 import session_with_user, user_by_email


@dataclass(frozen=True, repr=False)
class SessionContext:
    session: UserSession
    user: AppUser
    raw_token: str


def authenticate_session(db: Session, raw_token: str | None) -> SessionContext:
    if raw_token is None or re.fullmatch(r"[A-Za-z0-9_-]{43}", raw_token) is None:
        raise AppError(401, "SESSION_INVALID", "Inicia sesión para continuar.")
    token_digest = digest_token(raw_token)
    found = session_with_user(db, token_digest)
    if found is None:
        raise AppError(401, "SESSION_INVALID", "Inicia sesión para continuar.")
    session, user = found
    if (
        not hmac.compare_digest(session.token_digest, token_digest)
        or session.revoked_at is not None
        or session.expires_at <= datetime.now(UTC)
        or not user.is_active
    ):
        raise AppError(401, "SESSION_INVALID", "La sesión ya no está disponible. Inicia sesión nuevamente.")
    return SessionContext(session=session, user=user, raw_token=raw_token)


def session_csrf(context: SessionContext, settings: Settings) -> str:
    token = csrf_token_for_session(context.raw_token, settings.csrf_key)
    if not hmac.compare_digest(context.session.csrf_digest, digest_token(token)):
        raise AppError(401, "SESSION_INVALID", "La sesión ya no está disponible. Inicia sesión nuevamente.")
    return token


def check_csrf(context: SessionContext, token: str | None, settings: Settings) -> None:
    expected = session_csrf(context, settings)
    if (
        token is None
        or re.fullmatch(r"[0-9a-f]{64}", token) is None
        or not hmac.compare_digest(expected, token)
        or not hmac.compare_digest(context.session.csrf_digest, digest_token(token))
    ):
        raise AppError(403, "CSRF_INVALID", "La solicitud no tiene un token de seguridad válido.")


def login(
    db: Session,
    *,
    email: str,
    password: str,
    settings: Settings,
    request_id: UUID,
    previous_token: str | None = None,
) -> SessionContext:
    user = user_by_email(db, email.lower())
    valid_password = password_verify(password, user.password_hash if user else None)
    if user is None or not valid_password or not user.is_active:
        raise AppError(401, "INVALID_CREDENTIALS", "El correo o la contraseña no son válidos.")
    now = datetime.now(UTC)
    # Sustituir una sesión del mismo usuario revoca la cookie anterior sin reutilizarla.
    if previous_token and len(previous_token) <= 128:
        previous = session_with_user(db, digest_token(previous_token))
        if previous and previous[0].user_id == user.id and previous[0].revoked_at is None:
            previous[0].revoked_at = now
            db.add(AuditEvent(
                actor_id=user.id,
                entity_type="user_session",
                entity_id=previous[0].id,
                action="SESSION_REPLACED",
                request_id=request_id,
                payload={"scope": "ACCOUNT_ACCESS"},
            ))
    raw_token = new_session_token()
    csrf_token = csrf_token_for_session(raw_token, settings.csrf_key)
    session = UserSession(
        user_id=user.id,
        token_digest=digest_token(raw_token),
        csrf_digest=digest_token(csrf_token),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
    )
    db.add(session)
    db.flush()
    db.add(AuditEvent(
        actor_id=user.id,
        entity_type="user_session",
        entity_id=session.id,
        action="SESSION_CREATED",
        request_id=request_id,
        payload={"scope": "ACCOUNT_ACCESS"},
    ))
    db.commit()
    return SessionContext(session=session, user=user, raw_token=raw_token)


def logout(db: Session, context: SessionContext, event_request_id: UUID) -> None:
    result = db.execute(
        update(UserSession)
        .where(UserSession.id == context.session.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    if result.rowcount != 1:
        raise AppError(401, "SESSION_INVALID", "La sesión ya no está disponible.")
    db.add(AuditEvent(
        actor_id=context.user.id,
        entity_type="user_session",
        entity_id=context.session.id,
        action="SESSION_REVOKED",
        request_id=event_request_id,
        payload={"scope": "ACCOUNT_ACCESS"},
    ))
    db.commit()
