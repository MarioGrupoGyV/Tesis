"""Protocolo REAL y riesgo de referencia. Sin consentimientos, documentos ni autorizadores."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
# Tablas a las que apunta por FK (periodos, usuarios, matrículas y cortes): registradas aunque el proceso no importe la aplicación completa.
from app.models import s1, s2  # noqa: F401


class ProcessingProtocolRecord(Base):
    __tablename__ = 'processing_protocols'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    period_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.academic_periods.id'))
    data_origin: Mapped[str] = mapped_column(Text, default='REAL')
    school_label: Mapped[str] = mapped_column(Text)
    cohort_label: Mapped[str] = mapped_column(Text)
    grade_scale_min: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    grade_scale_max: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    participation_min: Mapped[int] = mapped_column(SmallInteger)
    participation_max: Mapped[int] = mapped_column(SmallInteger)
    participation_labels: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    bimesters: Mapped[list] = mapped_column(JSONB)
    source_label: Mapped[str] = mapped_column(Text)
    quality_rules: Mapped[dict] = mapped_column(JSONB)
    eligibility_rules: Mapped[dict] = mapped_column(JSONB)
    risk_rule: Mapped[dict] = mapped_column(JSONB)
    opportune_windows: Mapped[dict] = mapped_column(JSONB)
    authorization_confirmed_by_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey('risk_school.app_users.id'))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[UUID] = mapped_column(ForeignKey('risk_school.app_users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskReferenceRecord(Base):
    __tablename__ = 'risk_references'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.enrollments.id'))
    period_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.academic_periods.id'))
    data_origin: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.academic_snapshots.id'))
    bimester: Mapped[str] = mapped_column(Text)
    rule_version: Mapped[str] = mapped_column(Text)
    closing_date: Mapped[date] = mapped_column(Date)
    closing_available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    average_grade: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    days_scheduled: Mapped[int] = mapped_column(Integer)
    days_attended: Mapped[int] = mapped_column(Integer)
    activities_scheduled: Mapped[int] = mapped_column(Integer)
    activities_delivered: Mapped[int] = mapped_column(Integer)
    participation_level: Mapped[int | None] = mapped_column(SmallInteger)      # NULL en RIESGO_V2
    behavior_incidents: Mapped[int] = mapped_column(Integer)
    points_grade: Mapped[int] = mapped_column(SmallInteger)
    points_attendance: Mapped[int] = mapped_column(SmallInteger)
    points_activities: Mapped[int] = mapped_column(SmallInteger)
    points_participation: Mapped[int | None] = mapped_column(SmallInteger)     # NULL en RIESGO_V2
    points_conduct: Mapped[int] = mapped_column(SmallInteger)
    total_points: Mapped[int] = mapped_column(SmallInteger)
    risk_level: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey('risk_school.risk_references.id'))
    computed_by: Mapped[UUID] = mapped_column(ForeignKey('risk_school.app_users.id'))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
