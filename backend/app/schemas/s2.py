"""Proyecciones públicas S2. Los campos privados nunca se serializan."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, PlainSerializer, StrictInt
from app.schemas.s1 import ContractModel

Number = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Origin = Literal["REAL", "SYNTHETIC"]
Risk = Literal["LOW", "MEDIUM", "HIGH"]


class ImportErrorItem(ContractModel):
    row: int = Field(ge=1)
    column: str
    code: str
    message: str


class ImportBatch(ContractModel):
    id: UUID
    period_id: UUID
    data_origin: Origin
    file_name: str
    file_sha256: str
    schema_version: str
    status: Literal["PREVIEW", "READY", "COMMITTED", "FAILED"]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    planned_students: int
    planned_enrollments: int
    planned_snapshots: int
    preview_version: int
    errors: list[ImportErrorItem]
    created_at: datetime
    committed_at: datetime | None


class CommitInput(ContractModel):
    expected_preview_version: StrictInt = Field(ge=1)


class ImportCommit(ContractModel):
    batch_id: UUID
    status: Literal["COMMITTED"] = "COMMITTED"
    created_snapshots: int
    reused_result: bool


class Snapshot(ContractModel):
    id: UUID
    enrollment_id: UUID
    period_id: UUID
    data_origin: Origin
    window_start: date
    cutoff_at: datetime
    available_at: datetime
    target_date: date
    revision: int
    supersedes_id: UUID | None
    average_grade: Number | None
    attendance_pct: Number | None
    activities_pct: Number | None
    participation_level: int | None
    behavior_incidents: int | None
    age_years: int | None
    missing_fraction: Number


class Prediction(ContractModel):
    id: UUID
    enrollment_id: UUID
    snapshot_id: UUID
    model_id: UUID
    data_origin: Origin
    risk_level: Risk
    cutoff_at: datetime
    target_date: date
    predicted_at: datetime
    probability_low: Number | None
    probability_medium: Number | None
    probability_high: Number | None
    probabilities_calibrated: bool


class Student(ContractModel):
    id: UUID
    anon_code: str
    enrollment_id: UUID
    period_id: UUID
    section_id: UUID
    section_code: str
    grade: int
    data_origin: Origin
    average_grade: Number | None
    attendance_pct: Number | None
    latest_cutoff_at: datetime | None
    risk_level: Risk | None
    evaluation_status: Literal["EVALUATED", "NOT_EVALUATED", "INSUFFICIENT_DATA"]
    active_alert_id: UUID | None


class Alert(ContractModel):
    id: UUID
    enrollment_id: UUID
    student_id: UUID
    anon_code: str
    prediction_id: UUID
    data_origin: Origin
    severity: Literal["MEDIUM", "HIGH"]
    status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"]
    assigned_to: UUID | None
    resolution_reason: str | None
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    version: int


class Intervention(ContractModel):
    id: UUID
    enrollment_id: UUID
    alert_id: UUID | None
    data_origin: Origin
    kind: Literal["TUTORING", "REINFORCEMENT", "FAMILY_MEETING", "OTHER"]
    objective: str
    status: Literal["PLANNED", "DONE", "CANCELLED"]
    scheduled_at: datetime
    performed_at: datetime | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class StudentDetail(ContractModel):
    student: Student
    latest_snapshot: Snapshot | None
    latest_prediction: Prediction | None
    alerts: list[Alert]
    interventions: list[Intervention]


class StudentPage(ContractModel):
    items: list[Student]
    total: int
    page: int
    page_size: int


class TimelineEvent(ContractModel):
    id: UUID
    event_type: Literal["SNAPSHOT", "PREDICTION", "ALERT", "INTERVENTION"]
    occurred_at: datetime
    summary: str
    entity_id: UUID


class TimelineEventPage(ContractModel):
    items: list[TimelineEvent]
    total: int
    page: int
    page_size: int
