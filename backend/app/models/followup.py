"""Mapeo explícito del seguimiento existente y evidencia S5; nunca autogenera DDL."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AlertRecord(Base):
    __tablename__ = 'alerts'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.enrollments.id'))
    prediction_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.predictions.id'))
    data_origin: Mapped[str] = mapped_column(Text)
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey('risk_school.app_users.id'))
    severity: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default='OPEN')
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)


class InterventionRecord(Base):
    __tablename__ = 'interventions'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.enrollments.id'))
    alert_id: Mapped[UUID | None] = mapped_column(ForeignKey('risk_school.alerts.id'))
    data_origin: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey('risk_school.app_users.id'))
    kind: Mapped[str] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default='PLANNED')
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    creation_key: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    creation_payload_sha256: Mapped[str | None] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FollowupDecisionRecord(Base):
    __tablename__ = 'followup_decisions'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    prediction_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.predictions.id'), unique=True)
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.enrollments.id'))
    data_origin: Mapped[str] = mapped_column(Text)
    study_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.synthetic_studies.id'))
    alert_id: Mapped[UUID | None] = mapped_column(ForeignKey('risk_school.alerts.id'))
    decision: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
