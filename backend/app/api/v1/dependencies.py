from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.auth import SessionContext, authenticate_session


DbSession = Annotated[Session, Depends(get_db)]


def get_session_context(request: Request, db: DbSession) -> SessionContext:
    return authenticate_session(db, request.cookies.get("session"))


AuthenticatedSession = Annotated[SessionContext, Depends(get_session_context)]
