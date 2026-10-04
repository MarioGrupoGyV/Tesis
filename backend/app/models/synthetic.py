"""Registro privado mínimo; resultados/etiquetas permanecen fuera del checkout."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import CHAR, DateTime, ForeignKey, BigInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SyntheticStudyRecord(Base):
    __tablename__ = 'synthetic_studies'
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    period_id: Mapped[UUID] = mapped_column(ForeignKey('risk_school.academic_periods.id'))
    data_origin: Mapped[str] = mapped_column(Text)
    generator_version: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(BigInteger)
    config: Mapped[dict] = mapped_column(JSONB)
    manifest: Mapped[dict] = mapped_column(JSONB)
    csv_sha256: Mapped[str] = mapped_column(CHAR(64))
    storage_key: Mapped[str] = mapped_column(Text)
    payload_sha256: Mapped[str] = mapped_column(CHAR(64))
    bindings: Mapped[list] = mapped_column(JSONB, default=list)
    comparison: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey('risk_school.app_users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
