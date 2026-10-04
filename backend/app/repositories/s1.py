from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.s1 import AcademicPeriod, AppUser, GradeSection, UserSession


def user_by_email(db: Session, email: str) -> AppUser | None:
    return db.scalar(select(AppUser).where(AppUser.email == email))


def session_with_user(db: Session, token_digest: str) -> tuple[UserSession, AppUser] | None:
    row = db.execute(
        select(UserSession, AppUser)
        .join(AppUser, AppUser.id == UserSession.user_id)
        .where(UserSession.token_digest == token_digest)
    ).first()
    return (row[0], row[1]) if row is not None else None


def period_by_id(db: Session, period_id: UUID) -> AcademicPeriod | None:
    return db.get(AcademicPeriod, period_id)


def institutional_periods(db: Session, tutor_id: UUID | None = None) -> list[AcademicPeriod]:
    query = select(AcademicPeriod).where(AcademicPeriod.data_origin == "REAL")
    if tutor_id is not None:
        query = query.where(
            exists(select(GradeSection.id).where(
                GradeSection.school_year == AcademicPeriod.school_year,
                GradeSection.tutor_id == tutor_id,
            ))
        )
    return list(db.scalars(query.order_by(AcademicPeriod.school_year.desc(), AcademicPeriod.start_date, AcademicPeriod.id)))


def sections_for_year(db: Session, school_year: int, tutor_id: UUID | None = None) -> list[GradeSection]:
    query = select(GradeSection).where(GradeSection.school_year == school_year)
    if tutor_id is not None:
        query = query.where(GradeSection.tutor_id == tutor_id)
    return list(db.scalars(query.order_by(GradeSection.grade, GradeSection.code, GradeSection.id)))
