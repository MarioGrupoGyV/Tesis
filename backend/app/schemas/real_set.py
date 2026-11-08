"""Conjunto real cerrado (Bloque 10, ADR 015): consulta de solo lectura de los estudiantes de un periodo REAL.

Solo códigos; nunca nombres. Cada bimestre muestra la revisión de mitad de bimestre que usó la referencia RIESGO_V2,
el nivel que estimó el modelo REAL activo sobre ese corte y el nivel de referencia del fin del bimestre.
"""
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime
from app.schemas.s1 import ContractModel

Risk = Literal['LOW', 'MEDIUM', 'HIGH']


class RealSetCut(ContractModel):
    bimester: str
    cutoff_at: AwareDatetime | None
    average_grade: float | None
    attendance_pct: float | None
    activities_pct: float | None
    behavior_incidents: int | None
    predicted_risk: Risk | None
    reference_risk: Risk | None
    reference_points: int | None


class RealSetStudent(ContractModel):
    student_id: UUID
    anon_code: str
    grade: int
    section_code: str
    alert_status: Literal['OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'] | None
    cuts: list[RealSetCut]


class RealSetLevels(ContractModel):
    bimester: str
    cuts: int
    predicted_low: int
    predicted_medium: int
    predicted_high: int
    predicted_missing: int
    reference_low: int
    reference_medium: int
    reference_high: int


class RealSetPage(ContractModel):
    period_id: UUID
    period_code: str
    is_locked: bool
    model_algorithm: str | None
    bimesters: list[str]
    summary: list[RealSetLevels]
    students: int
    alerts: int
    items: list[RealSetStudent]
    total: int
    page: int
    page_size: int
