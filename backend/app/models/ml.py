"""Mapeo explícito de tablas existentes; no crea ni migra metadata parcial."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CHAR, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from app.models import s1, s2


class ModelVersion(Base):
    __tablename__ = 'model_versions'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),primary_key=True,default=uuid4)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    algorithm: Mapped[str] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text)
    dataset_hash: Mapped[str] = mapped_column(CHAR(64))
    artifact_sha256: Mapped[str] = mapped_column(CHAR(64))
    artifact_key: Mapped[str] = mapped_column(Text)
    feature_schema_version: Mapped[str] = mapped_column(Text)
    reference_criterion_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean,default=False)
    parameters: Mapped[dict] = mapped_column(JSONB)
    metrics: Mapped[dict] = mapped_column(JSONB)
    manifest: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey('risk_school.app_users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())


class PredictionRecord(Base):
    __tablename__ = 'predictions'
    __table_args__ = (UniqueConstraint('snapshot_id','model_id'),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),primary_key=True,default=uuid4)
    enrollment_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.enrollments.id'))
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.academic_snapshots.id'))
    model_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.model_versions.id'))
    data_origin: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(Text)
    probability_low: Mapped[Decimal | None] = mapped_column(Numeric(8,7))
    probability_medium: Mapped[Decimal | None] = mapped_column(Numeric(8,7))
    probability_high: Mapped[Decimal | None] = mapped_column(Numeric(8,7))
    probabilities_calibrated: Mapped[bool] = mapped_column(Boolean,default=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
