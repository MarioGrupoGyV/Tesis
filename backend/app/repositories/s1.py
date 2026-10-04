from uuid import UUID

from sqlalchemy import exists, select, text
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
    query = select(AcademicPeriod).where(AcademicPeriod.data_origin.in_(("REAL", "SYNTHETIC")))
    if tutor_id is not None:
        query = query.where(
            exists(select(GradeSection.id).where(
                GradeSection.school_year == AcademicPeriod.school_year,
                GradeSection.tutor_id == tutor_id,
            ))
        )
    rows=list(db.scalars(query.order_by(AcademicPeriod.school_year.desc(), AcademicPeriod.start_date, AcademicPeriod.id)))
    return [p for p in rows if not tutor_id or sections_for_period(db,p,tutor_id)]


def sections_for_year(db: Session, school_year: int, tutor_id: UUID | None = None) -> list[GradeSection]:
    query = select(GradeSection).where(GradeSection.school_year == school_year)
    if tutor_id is not None:
        query = query.where(GradeSection.tutor_id == tutor_id)
    return list(db.scalars(query.order_by(GradeSection.grade, GradeSection.code, GradeSection.id)))


def sections_for_period(db,period,tutor_id=None):
    # Catálogo heredado sin origen: separar las secciones registradas del estudio,
    # incluso cuando un contexto REAL comparte el año. No inferir por un prefijo.
    comparison='EXISTS' if period.data_origin=='SYNTHETIC' else 'NOT EXISTS'
    match='AND st.period_id=:period' if period.data_origin=='SYNTHETIC' else ''
    tutor='AND g.tutor_id=:tutor' if tutor_id else ''
    sql=f'''SELECT g.* FROM risk_school.grade_sections g WHERE g.school_year=:year {tutor}
        AND {comparison}(SELECT 1 FROM risk_school.synthetic_studies st,
            jsonb_array_elements(st.manifest->'context'->'sections') section
            WHERE (st.config->>'school_year')::integer=g.school_year {match}
              AND section->>'code'=g.code AND (section->>'grade')::integer=g.grade)
        ORDER BY g.grade,g.code,g.id'''
    return list(db.scalars(select(GradeSection).from_statement(text(sql)),
        {'year':period.school_year,'period':period.id,'tutor':tutor_id}))
