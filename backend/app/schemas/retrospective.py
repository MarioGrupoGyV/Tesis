from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Risk = Literal['LOW', 'MEDIUM', 'HIGH']


class RetroModel(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


class RetrospectiveMetrics(RetroModel):
    n: int
    correct: int
    accuracy: float
    f1_macro: float
    confusion: list[list[int]]
    support: list[int]
    alert_proposals: int


class RetrospectiveSummary(RetroModel):
    id: UUID
    executed_at: AwareDatetime
    completed_at: AwareDatetime
    scope: Literal['RETROSPECTIVE_EVALUATION']
    data_origin: Literal['REAL_USER_AUTHORIZED_UNVERIFIED']
    algorithm: Literal['SVM']
    training_term: Literal['B1']
    evaluation_term: Literal['B2']
    cutoffs: dict[str, str]
    feature_order: list[str]
    refitted: Literal[False]
    scaler_b1_verified: bool
    b1_support_vectors_verified: bool
    source_events_verified: bool
    temporal_check: Literal['DERIVED_AGGREGATE_ONLY', 'SOURCE_DECLARED_EVENTS_VERIFIED']
    same_cohort: Literal[True]
    compatibility: Literal['CROSS_VERSION_EXPERIMENTAL', 'SOURCE_SKLEARN_VERSION']
    version_warnings: list[str]
    versions: dict[str, str]
    source_versions: dict[str, str]
    metrics: RetrospectiveMetrics
    prediction_mismatches: int
    discrepancies: list[str]
    missing_package_files: list[str]
    notifications_sent: Literal[0]
    interventions_performed: Literal[0]


class RetrospectivePrediction(RetroModel):
    row_number: int
    risk_level: Risk
    reference_risk: Risk
    correct: bool
    alert_proposed: bool
    matches_package: bool
    probabilities_calibrated: Literal[False]
    notification_sent: Literal[False]
    intervention_performed: Literal[False]


class RetrospectiveDetail(RetrospectiveSummary):
    predictions: list[RetrospectivePrediction]


class RetrospectivePage(RetroModel):
    available: bool
    items: list[RetrospectiveSummary]
    total: int
    page: int
    page_size: int


class PartialValues(RetroModel):
    promedio_parcial_0_20: float = Field(ge=0, le=20, allow_inf_nan=False)
    asistencia_parcial_proporcion: float = Field(ge=0, le=1, allow_inf_nan=False)
    entrega_parcial_proporcion: float = Field(ge=0, le=1, allow_inf_nan=False)


class PartialAvailability(RetroModel):
    promedio_parcial_0_20: AwareDatetime
    asistencia_parcial_proporcion: AwareDatetime
    entrega_parcial_proporcion: AwareDatetime


class RetrospectivePartialInput(RetroModel):
    term: Literal['B1', 'B2']
    values: PartialValues
    available_at: PartialAvailability


class RetrospectivePartialResult(RetroModel):
    executed_at: AwareDatetime
    scope: Literal['RETROSPECTIVE_EVALUATION']
    risk_level: Risk
    alert_proposed: bool
    probabilities_calibrated: Literal[False]
    notification_sent: Literal[False]
    intervention_performed: Literal[False]
