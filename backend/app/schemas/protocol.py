"""Contrato del protocolo REAL (ADR 012 §6.1). Sin consentimientos, documentos, autorizadores ni fechas de permiso."""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from uuid import UUID
from pydantic import AfterValidator, AwareDatetime, Field, StrictInt, field_validator, model_validator
from app.schemas.s1 import ContractModel

Code = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,20}$')]
Label = Annotated[str, Field(min_length=1, max_length=120)]


def two_places(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


Scale = Annotated[Decimal, AfterValidator(two_places)]


class Bimester(ContractModel):
    code: Code
    start_date: date
    cutoff_date: date
    cutoff_available_at: AwareDatetime
    close_date: date
    closing_available_at: AwareDatetime
    scheduled_days: StrictInt = Field(ge=1, le=366)

    @model_validator(mode='after')
    def ordered(self):
        if not self.start_date <= self.cutoff_date < self.close_date:
            raise ValueError('Inicio ≤ corte < cierre.')
        if self.cutoff_available_at.date() < self.cutoff_date or self.closing_available_at.date() < self.close_date:
            raise ValueError('La disponibilidad no puede preceder a su fecha.')
        return self


class EligibilityRules(ContractModel):
    inference_max_missing_fraction: float = Field(ge=0, lt=1)
    required_features: list[str] = Field(min_length=1, max_length=5)


class RiskRule(ContractModel):
    version: Literal['RIESGO_V1']


class OpportuneWindows(ContractModel):
    detection_days: StrictInt = Field(ge=0, le=60)
    intervention_days: StrictInt = Field(ge=0, le=60)


class ProtocolParams(ContractModel):
    school_label: Label
    cohort_label: Label
    grade_scale_min: Scale
    grade_scale_max: Scale
    participation_min: StrictInt = Field(ge=0, le=10)
    participation_max: StrictInt = Field(ge=1, le=10)
    participation_labels: dict[str, Annotated[str, Field(max_length=60)]] | None = None
    bimesters: list[Bimester] = Field(min_length=1, max_length=8)
    source_label: Annotated[str, Field(min_length=1, max_length=160)]
    quality_rules: dict = Field(default_factory=dict)
    eligibility_rules: EligibilityRules
    risk_rule: RiskRule
    opportune_windows: OpportuneWindows

    @model_validator(mode='after')
    def coherent(self):
        if self.grade_scale_min >= self.grade_scale_max or self.participation_min >= self.participation_max:
            raise ValueError('Las escalas deben ir de menor a mayor.')
        if len({item.code for item in self.bimesters}) != len(self.bimesters):
            raise ValueError('Los códigos de bimestre deben ser únicos.')
        if self.participation_labels and any(not self.participation_min <= int(key) <= self.participation_max
                                              for key in self.participation_labels if key.isdigit()):
            raise ValueError('Etiqueta de participación fuera de escala.')
        return self

    @field_validator('quality_rules')
    @classmethod
    def small(cls, value):
        if len(str(value)) > 4000:
            raise ValueError('Reglas de calidad demasiado extensas.')
        return value


class ProtocolCreate(ProtocolParams):
    period_id: UUID


class Protocol(ProtocolParams):
    id: UUID
    period_id: UUID
    authorization_confirmed_by_admin: bool
    confirmed_by: UUID | None
    confirmed_at: datetime | None
    version: int
    created_at: datetime
