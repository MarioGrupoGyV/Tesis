from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, Field
from app.schemas.s1 import ContractModel
from app.schemas.s5 import FollowupResult


class Model(ContractModel):
    id: UUID
    name: str
    version: str
    algorithm: Literal['DUMMY','RANDOM_FOREST','SVM','XGBOOST']
    data_origin: Literal['REAL','SYNTHETIC']
    feature_schema_version: str
    reference_criterion_version: str
    status: Literal['DRAFT','EVALUATED','APPROVED','RETIRED']
    is_active: bool
    created_at: datetime
    # Alcance y aprobación: SYNTHETIC_STUDY/TECHNICAL_SIMULATION o INSTITUTIONAL_STUDY/LOCAL_EXPLORATORY (sin validación externa).
    scope: str | None = None
    approval_kind: str | None = None
    warnings: list[str] = []


class ModelPage(ContractModel):
    items: list[Model]
    total: int
    page: int
    page_size: int


class PredictionRunInput(ContractModel):
    period_id: UUID
    as_of: AwareDatetime


class Abstention(ContractModel):
    snapshot_id: UUID
    status: Literal['MODEL_NOT_AVAILABLE','INSUFFICIENT_DATA','INELIGIBLE','INCOMPATIBLE']
    reason: str


class PredictionRunResult(ContractModel):
    period_id: UUID
    as_of: datetime
    model_id: UUID
    selected: int
    created: int
    reused: int
    abstentions: list[Abstention]
    followup: FollowupResult


class StudentEvaluation(ContractModel):
    """Resultado de evaluar la última medición de una matrícula (simulación)."""
    status: Literal['EVALUATED','INSUFFICIENT_DATA','NOT_ELIGIBLE']
    risk_level: Literal['LOW','MEDIUM','HIGH'] | None = None
    reason: str | None = None
    snapshot_id: UUID
    prediction_id: UUID | None = None
    prediction_reused: bool = False
    case_action: Literal['CREATED','UPDATED','REUSED','NONE'] = 'NONE'
    alert_id: UUID | None = None
