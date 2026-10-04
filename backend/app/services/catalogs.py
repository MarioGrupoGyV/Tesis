from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.s1 import AcademicPeriod, AppUser, GradeSection
from app.repositories.s1 import demo_periods, period_by_id, sections_for_year


def require_catalog_role(user: AppUser) -> None:
    if user.role not in {"ADMIN", "TUTOR", "DIRECTOR"}:
        raise AppError(403, "FORBIDDEN", "Tu rol no tiene acceso a este recurso.")


def periods(db: Session, user: AppUser) -> list[AcademicPeriod]:
    require_catalog_role(user)
    return demo_periods(db, user.id if user.role == "TUTOR" else None)


def sections(db: Session, user: AppUser, period_id: UUID) -> list[GradeSection]:
    require_catalog_role(user)
    period = period_by_id(db, period_id)
    if period is None:
        raise AppError(404, "PERIOD_NOT_FOUND", "El periodo solicitado no está disponible.")
    authorized = sections_for_year(db, period.school_year, user.id if user.role == "TUTOR" else None)
    if user.role == "TUTOR" and not authorized:
        raise AppError(403, "FORBIDDEN", "No tienes secciones asignadas en este periodo.")
    if period.data_origin != "DEMO":
        raise AppError(422, "REAL_MODE_NOT_READY", "El procesamiento de datos reales aún no está habilitado.")
    return authorized
