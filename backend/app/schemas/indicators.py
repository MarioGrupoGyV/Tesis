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
    total: int | None
    students: int | None
    mean: float | None
    median: float | None
    alerted_students: int | None
    mean_alerted: float | None
    median_alerted: float | None
    reason: str | None = None


class Opportune(Ratio):
    window_days: int
    median_days_to_first: float | None = None
    students_with_first_intervention: int = 0


class OpportuneByIntervention(Ratio):
    """Por intervención (comparable con la Tabla 6): realizadas ligadas a alerta dentro de la ventana ÷ realizadas ligadas."""
    window_days: int
    without_alert: int


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
    # Validación cruzada: repeticiones y desviación estándar de las métricas macro (null en el cálculo en memoria).
    repetitions: int | None = None
    macro_sd: dict[str, float | None] | None = None


class Spread(ContractModel):
    """Media y desviación entre las repeticiones de la validación cruzada, en porcentaje."""
    mean: float | None
    sd: float | None


class DetectionCounts(ContractModel):
    """Conteos sumados de todas las repeticiones (cada observación se valida una vez por repetición)."""
    reference_at_risk: int
    detected: int
    reference_low: int
    low_flagged: int
    reference_medium: int
    medium_flagged: int
    reference_high: int
    high_flagged: int
    high_as_low: int


class ValidatedDetection(ContractModel):
    """Detección fuera de muestra: de las observaciones de referencia Medio/Alto, proporción que el modelo marcó Medio/Alto
    cuando el estudiante estaba en el pliegue de validación. `low_flagged` es la falsa alarma (Bajo marcado Medio/Alto)."""
    bimester: str | None = None
    repetitions: int
    reference_at_risk_per_repetition: int
    detection: Spread
    medium_detected: Spread
    high_detected: Spread
    high_as_low: Spread
    low_flagged: Spread
    pooled: DetectionCounts
    metric_basis: Literal['OUT_OF_FOLD'] = 'OUT_OF_FOLD'
    metric_label: str
    note: str


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
    opportune_by_intervention: OpportuneByIntervention
    performance: Performance
    model_metrics: ModelMetrics | None
    model_metrics_reason: str | None = None
    # OUT_OF_FOLD: validación cruzada agrupada por estudiante (informe del modelo activo). IN_SAMPLE: en memoria, no valida el modelo.
    metric_basis: Literal['OUT_OF_FOLD', 'IN_SAMPLE'] | None = None
    metric_label: str | None = None
    in_sample_metrics: ModelMetrics | None = None
    # REAL: detección validada del modelo activo (solo periodo completo). null con motivo si no hay informe fuera de muestra.
    validated_detection: ValidatedDetection | None = None
    validated_detection_reason: str | None = None
    exclusions: Exclusions


class IndicatorsResponse(ContractModel):
    period_id: UUID
    period_code: str
    data_origin: Literal['SYNTHETIC', 'REAL']
    is_simulation: bool
    notice: str
    bimester: str | None = None
    retrospective_alerts: int = 0
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
    alert_detected_at: datetime | None = None
    retrospective: bool = False
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
    """Periodo con estudio registrado (SYNTHETIC; REAL solo con protocolo confirmado) y sus secciones autorizadas."""
    period_id: UUID
    period_code: str
    school_year: int
    is_locked: bool
    data_origin: Literal['SYNTHETIC', 'REAL'] = 'SYNTHETIC'
    bimesters: list[str] = []
    sections: list[ContextSection]


class InterventionIndicator(ContractModel):
    anon_code: str
    grade: int
    section_code: str
    alert_opened_at: datetime | None
    performed_at: datetime
    days_since_alert: int | None
    opportune: bool | None
