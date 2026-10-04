from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.s1 import Health

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=Health, operation_id="live")
def live() -> Health:
    return Health(status="ok")


@router.get("/ready", response_model=Health, operation_id="ready", responses={503: {"model": Health}})
def ready(request: Request) -> Health | JSONResponse:
    try:
        with request.app.state.database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return Health(status="ok")
