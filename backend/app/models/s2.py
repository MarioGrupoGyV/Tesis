"""Entidades S2 sobre las tablas existentes; sin DDL en el arranque."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CHAR, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models import s1  # Registrar los destinos de FK en la misma metadata.


class StudentRecord(Base):
    __tablename__ = "students"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    anon_code: Mapped[str] = mapped_column(Text, nullable=False)
    data_origin: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    eligible_for_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_documented: Mapped[bool] = mapped_column(Boolean, default=False)
    assent_documented: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EnrollmentRecord(Base):
    __tablename__ = "enrollments"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.students.id"))
    period_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.academic_periods.id"))
    section_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.grade_sections.id"))
    data_origin: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportBatchRecord(Base):
    __tablename__ = "import_batches"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    study_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    period_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.academic_periods.id"))
    data_origin: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("risk_school.app_users.id"))
    file_name: Mapped[str] = mapped_column(Text)
    file_sha256: Mapped[str] = mapped_column(CHAR(64))
    schema_version: Mapped[str] = mapped_column(Text, default="academic-v1")
    storage_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    total_rows: Mapped[int] = mapped_column(Integer)
    valid_rows: Mapped[int] = mapped_column(Integer)
    invalid_rows: Mapped[int] = mapped_column(Integer)
    planned_students: Mapped[int] = mapped_column(Integer)
    planned_enrollments: Mapped[int] = mapped_column(Integer)
    planned_snapshots: Mapped[int] = mapped_column(Integer)
    preview_version: Mapped[int] = mapped_column(Integer, default=1)
    preview_state: Mapped[list] = mapped_column(JSONB)
    errors: Mapped[list] = mapped_column(JSONB)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SnapshotRecord(Base):
    __tablename__ = "academic_snapshots"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.enrollments.id"))
    period_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.academic_periods.id"))
    data_origin: Mapped[str] = mapped_column(Text)
    import_batch_id: Mapped[UUID] = mapped_column(ForeignKey("risk_school.import_batches.id"))
    window_start: Mapped[date] = mapped_column(Date)
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_date: Mapped[date] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[UUID | None] = mapped_column(ForeignKey("risk_school.academic_snapshots.id"))
    average_grade: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    attendance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    activities_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    participation_level: Mapped[int | None] = mapped_column(SmallInteger)
    behavior_incidents: Mapped[int | None] = mapped_column(Integer)
    age_years: Mapped[int | None] = mapped_column(SmallInteger)
    missing_fraction: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    schema_version: Mapped[str] = mapped_column(Text, default="academic-v1")
    source_row_number: Mapped[int] = mapped_column(Integer)
    row_sha256: Mapped[str] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
