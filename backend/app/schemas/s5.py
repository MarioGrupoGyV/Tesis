"""Contrato público S5. Campos privados/idempotencia interna no se serializan."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field, StrictInt, model_validator
from app.schemas.s1 import ContractModel
from app.schemas.s2 import Alert, Intervention, Prediction, Snapshot, TimelineEvent

AlertStatus = Literal['OPEN','IN_REVIEW','RESOLVED','DISMISSED']
EvaluationStatus = Literal['EVALUATED','NOT_EVALUATED','INSUFFICIENT_DATA']

class SyncInput(ContractModel):
    period_id: UUID

class FollowupResult(ContractModel):
    policy_version: Literal['followup-policy-v1'] = 'followup-policy-v1'
    period_id: UUID
    created: int = 0
    updated: int = 0
    retained_low: int = 0
    no_alert: int = 0
    reused: int = 0
    ignored_stale: int = 0
    skipped_missing: int = 0

class CaseCapabilities(ContractModel):
    can_edit: bool
    can_plan: bool
    reason: str | None

class AlertCase(Alert):
    period_id: UUID
    section_id: UUID
    section_code: str
    grade: int
    assigned_display_name: str | None
    current_risk_level: Literal['LOW','MEDIUM','HIGH'] | None
    current_evaluation_status: EvaluationStatus
    latest_cutoff_at: datetime | None
    capabilities: CaseCapabilities

class AlertPage(ContractModel):
    items: list[AlertCase]
    total: int
    page: int
    page_size: int

class InterventionView(Intervention):
    can_edit: bool
    edit_block_reason: str | None

class AlertDetail(ContractModel):
    alert: AlertCase
    source_prediction: Prediction
    latest_snapshot: Snapshot | None
    latest_prediction: Prediction | None
    interventions: list[InterventionView]
    history: list[TimelineEvent]
    history_truncated: bool

class AlertPatch(ContractModel):
    expected_version: StrictInt = Field(ge=1)
    status: AlertStatus
    resolution_reason: str | None = Field(default=None,max_length=1000)

    @model_validator(mode='after')
    def closure(self):
        if self.status in ('RESOLVED','DISMISSED') and not (self.resolution_reason or '').strip():
            raise ValueError('Cerrar exige un motivo no vacío.')
        if self.status in ('OPEN','IN_REVIEW') and self.resolution_reason is not None:
            raise ValueError('El motivo de cierre solo corresponde a estados cerrados.')
        return self

class InterventionCreate(ContractModel):
    alert_id: UUID
    expected_alert_version: StrictInt = Field(ge=1)
    creation_key: UUID
    kind: Literal['TUTORING','REINFORCEMENT','FAMILY_MEETING','OTHER']
    objective: str = Field(min_length=1,max_length=1000)
    scheduled_at: AwareDatetime
    notes: str | None = Field(default=None,max_length=2000)

    @model_validator(mode='after')
    def objective_not_blank(self):
        if not self.objective.strip():
            raise ValueError('El objetivo no puede estar vacío.')
        return self

class InterventionCreateResult(ContractModel):
    intervention: InterventionView
    reused_result: bool

class InterventionPatch(ContractModel):
    expected_version: StrictInt = Field(ge=1)
    kind: Literal['TUTORING','REINFORCEMENT','FAMILY_MEETING','OTHER'] | None = None
    objective: str | None = Field(default=None,min_length=1,max_length=1000)
    scheduled_at: AwareDatetime | None = None
    notes: str | None = Field(default=None,max_length=2000)
    status: Literal['PLANNED','DONE','CANCELLED'] | None = None
    performed_at: AwareDatetime | None = None

    @model_validator(mode='after')
    def check_values(self):
        if self.objective is not None and not self.objective.strip():
            raise ValueError('El objetivo no puede estar vacío.')
        if self.status == 'DONE' and self.performed_at is None:
            raise ValueError('Realizada exige fecha efectiva con zona.')
        if self.status != 'DONE' and self.performed_at is not None:
            raise ValueError('Fecha efectiva solo corresponde a realizada.')
        if not (self.model_fields_set - {'expected_version'}):
            raise ValueError('Envía al menos un cambio.')
        return self

class ReportRow(ContractModel):
    student_id: UUID
    enrollment_id: UUID
    anon_code: str
    section_id: UUID
    section_code: str
    grade: int
    latest_cutoff_at: datetime | None
    evaluation_status: EvaluationStatus
    risk_level: Literal['LOW','MEDIUM','HIGH'] | None
    active_alert_id: UUID | None
    active_alert_status: Literal['OPEN','IN_REVIEW'] | None
    cases_open: int
    cases_in_review: int
    cases_resolved: int
    cases_dismissed: int
    interventions_planned: int
    interventions_done: int
    interventions_cancelled: int

class Percentage(ContractModel):
    count: int
    denominator: int
    percentage: float | None
    reason: str | None

class EvaluationCounts(ContractModel):
    evaluated: int
    not_evaluated: int
    insufficient_data: int

class RiskCounts(ContractModel):
    low: Percentage
    medium: Percentage
    high: Percentage

class CaseCounts(ContractModel):
    open: int
    in_review: int
    resolved: int
    dismissed: int
    active_enrollments: int

class InterventionCounts(ContractModel):
    planned: int
    done: int
    cancelled: int

class ReportSummary(ContractModel):
    period_id: UUID
    period_code: str
    section_id: UUID | None
    authorized_section_ids: list[UUID]
    scope: Literal['SYNTHETIC_STUDY'] = 'SYNTHETIC_STUDY'
    data_origin: Literal['SYNTHETIC'] = 'SYNTHETIC'
    notice: str
    generated_at: datetime
    cutoff_min: datetime | None
    cutoff_max: datetime | None
    total: int
    evaluations: EvaluationCounts
    risks: RiskCounts
    cases: CaseCounts
    interventions: InterventionCounts
    items: list[ReportRow]
    page: int
    page_size: int
