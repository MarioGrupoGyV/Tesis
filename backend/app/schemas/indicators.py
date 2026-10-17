"""Contrato público de indicadores de la tesis. Solo códigos anónimos; nunca nombres."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime
from app.schemas.s1 import ContractModel

Risk = Literal['LOW', 'MEDIUM', 'HIGH']


class Ratio(ContractModel):
    """Numerador y denominador siempre visibles; percent es null sin denominador o sin fuente."""
    numerator: int | None
    denominator: int | None
    percent: float | None
    reason: str | None = None


class Prv(Ratio):
    received: int | None = None
    valid_processed: int | None = None
    rejected: int | None = None
    valid_not_committed: int | None = None
    ineligible_omitted: int | None = None
    manual_measurements: int | None = None


class Nia(ContractModel):
    total: int
    students: int
    mean: float | None
    median: float | None
    alerted_students: int
    mean_alerted: float | None
    median_alerted: float | None
    reason: str | None = None


class Opportune(Ratio):
    window_days: int
    median_days_to_first: float | None = None
    students_with_first_intervention: int = 0


class Descriptive(ContractModel):
    n: int
    mean: float | None
    sd: float | None
    median: float | None
    minimum: float | None
    maximum: float | None


class Performance(ContractModel):
    average_grade: Descriptive
    attendance_pct: Descriptive


class ClassMetric(ContractModel):
    support: int
    precision: float | None
    recall: float | None
    f1: float | None


class MacroMetrics(ContractModel):
    precision: float | None
    recall: float | None
    f1: float | None


class ModelMetrics(ContractModel):
    n: int
    class_order: list[str]
    confusion_matrix: list[list[int]]
    per_class: dict[str, ClassMetric]
    macro: MacroMetrics
    accuracy: float | None
    not_estimable_reasons: dict[str, str]


class Exclusions(ContractModel):
    ineligible: int
    no_snapshot: int
    no_reference: int
    reference_reason: str | None = None


class Summary(ContractModel):
    section_id: UUID | None
    section_code: str | None
    grade: int | None
    eligible_students: int
    cra: Ratio
    pder: Ratio
    nia: Nia
    opportune: Opportune
    performance: Performance
    model_metrics: ModelMetrics | None
    model_metrics_reason: str | None = None
    exclusions: Exclusions


class IndicatorsResponse(ContractModel):
    period_id: UUID
    period_code: str
    data_origin: Literal['SYNTHETIC']
    is_simulation: bool
    notice: str
    as_of: AwareDatetime
    close_at: AwareDatetime
    opportune_window_days: int
    section_id: UUID | None
    authorized_section_ids: list[UUID]
    prv: Prv
    total: Summary
    sections: list[Summary]


class StudentIndicator(ContractModel):
    anon_code: str
    grade: int
    section_code: str
    eligible: bool
    average_grade: float | None
    attendance_pct: float | None
    reference_risk: Risk | None
    predicted_risk: Risk | None
    alert_opened_at: datetime | None
    alert_before_close: bool | None
    nia: int
    opportune: bool | None
    days_to_first_intervention: int | None
    exclusion_reason: str | None


class StudentIndicatorPage(ContractModel):
    period_id: UUID
    as_of: AwareDatetime
    items: list[StudentIndicator]
    total: int
    page: int
    page_size: int


class ContextSection(ContractModel):
    id: UUID
    code: str
    grade: int


class IndicatorContext(ContractModel):
    """Periodo SYNTHETIC con estudio registrado y sus secciones autorizadas (incluye RESEARCHER)."""
    period_id: UUID
    period_code: str
    school_year: int
    is_locked: bool
    sections: list[ContextSection]
