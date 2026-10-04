"""Contrato interno ML v1. Metadatos y etiquetas nunca forman parte de X."""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

CLASSES = ('LOW', 'MEDIUM', 'HIGH')
BASE_FEATURES = ('average_grade', 'attendance_pct', 'activities_pct', 'participation_level', 'behavior_incidents')
LIMA = ZoneInfo('America/Lima')


class MLDiagnostic(ValueError):
    """Códigos sin valores/identificadores personales; no imprimir datasets."""


class InternalModel(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)


class Scale(InternalModel):
    minimum: float
    maximum: float
    decimals: int = Field(ge=0, le=6)
    unit: str = Field(min_length=1)

    @model_validator(mode='after')
    def ordered(self):
        if not np.isfinite([self.minimum, self.maximum]).all() or self.minimum >= self.maximum:
            raise ValueError('INVALID_SCALE')
        return self


class FeatureConfig(InternalModel):
    schema_version: Literal['ml-features-v1'] = 'ml-features-v1'
    snapshot_schema_version: Literal['academic-v1'] = 'academic-v1'
    criterion_version: str = Field(min_length=1)
    criterion_definition: str = Field(min_length=1)
    horizon_days: int = Field(ge=1, le=366)
    scales: dict[str, Scale]
    participation_values: list[int] = Field(min_length=2)
    extra_features: list[Literal['age_years', 'grade']] = Field(default_factory=list)
    extra_justification: str | None = None
    # No default: requiere decisión explícita; NO es elegibilidad de investigación.
    inference_max_missing_fraction: float = Field(ge=0, lt=1)
    required_features: list[str]

    @property
    def features(self):
        return (*BASE_FEATURES, *self.extra_features)

    @model_validator(mode='after')
    def consistent(self):
        if set(self.scales) != set(self.features) or len(set(self.extra_features)) != len(self.extra_features):
            raise ValueError('FEATURE_SCALES_REQUIRED')
        if self.extra_features and not (self.extra_justification or '').strip():
            raise ValueError('AGE_GRADE_JUSTIFICATION_REQUIRED')
        if not set(self.required_features) <= set(self.features):
            raise ValueError('UNKNOWN_REQUIRED_FEATURE')
        if len(set(self.participation_values)) != len(self.participation_values):
            raise ValueError('DUPLICATE_CATEGORIES')
        scale = self.scales['participation_level']
        if scale.decimals != 0 or any(not scale.minimum <= v <= scale.maximum for v in self.participation_values):
            raise ValueError('INVALID_PARTICIPATION_SCALE')
        return self


class Observation(InternalModel):
    student_key: str = Field(min_length=1, max_length=100)
    snapshot_id: UUID
    enrollment_id: UUID
    period_id: UUID
    data_origin: Literal['REAL']
    schema_version: Literal['academic-v1'] = 'academic-v1'
    revision: int = Field(ge=1)
    supersedes_id: UUID | None = None
    window_start: date
    available_at: AwareDatetime
    cutoff_at: AwareDatetime
    target_date: date
    created_at: AwareDatetime
    eligible: bool
    values: dict[str, float | None]
    feature_available_at: dict[str, AwareDatetime]
    input_provenance: str = Field(min_length=1)


class Label(InternalModel):
    snapshot_id: UUID
    risk: Literal['LOW', 'MEDIUM', 'HIGH']
    criterion_version: str = Field(min_length=1)
    outcome_definition: str = Field(min_length=1)
    provenance: str = Field(min_length=1)
    observed_at: AwareDatetime
    available_at: AwareDatetime


class Dataset(InternalModel):
    schema_version: Literal['ml-dataset-v1'] = 'ml-dataset-v1'
    scope: Literal['ISOLATED_TEST', 'INSTITUTIONAL']
    provenance: str = Field(min_length=1)
    evaluation_as_of: AwareDatetime
    config: FeatureConfig
    observations: list[Observation] = Field(min_length=1, max_length=10000)
    labels: list[Label]


def validate_observation(row: Observation, config: FeatureConfig):
    if row.schema_version != config.snapshot_schema_version:
        raise MLDiagnostic('SCHEMA_INCOMPATIBLE')
    day = row.cutoff_at.astimezone(LIMA).date()
    if row.available_at > row.cutoff_at or row.window_start > day or row.target_date <= day:
        raise MLDiagnostic('TEMPORAL_LEAKAGE')
    if (row.target_date - day).days != config.horizon_days:
        raise MLDiagnostic('HORIZON_INCOMPATIBLE')
    if set(row.values) != set(config.features) or set(row.feature_available_at) != set(config.features):
        raise MLDiagnostic('FEATURE_SCHEMA_INCOMPATIBLE')
    for name, value in row.values.items():
        if row.feature_available_at[name] > row.cutoff_at or row.feature_available_at[name] > row.available_at:
            raise MLDiagnostic('FEATURE_AVAILABLE_AFTER_CUTOFF')
        if value is None:
            continue
        scale = config.scales[name]
        if not np.isfinite(value) or not scale.minimum <= value <= scale.maximum:
            raise MLDiagnostic('OUT_OF_SCALE')
        if Decimal(str(value)).normalize().as_tuple().exponent < -scale.decimals:
            raise MLDiagnostic('DECIMAL_PRECISION')
        if name == 'participation_level' and value not in config.participation_values:
            raise MLDiagnostic('UNKNOWN_PARTICIPATION')


def validate_dataset(dataset: Dataset):
    config = dataset.config
    rows = {r.snapshot_id: r for r in dataset.observations}
    labels = {label.snapshot_id: label for label in dataset.labels}
    if len(rows) != len(dataset.observations) or len(labels) != len(dataset.labels):
        raise MLDiagnostic('DUPLICATE_OBSERVATION_OR_LABEL')
    if set(rows) != set(labels):
        raise MLDiagnostic('MISSING_OR_UNLINKED_LABEL')
    series = set()
    enrollment_students = {}
    for row in dataset.observations:
        validate_observation(row, config)
        if not row.eligible:
            raise MLDiagnostic('NOT_ELIGIBLE')
        if row.created_at > dataset.evaluation_as_of:
            raise MLDiagnostic('OBSERVATION_NOT_AVAILABLE')
        key = (row.enrollment_id, row.cutoff_at, row.revision)
        if key in series:
            raise MLDiagnostic('INCOMPATIBLE_DUPLICATE')
        series.add(key)
        identity = (row.student_key, row.period_id, row.data_origin)
        if enrollment_students.setdefault(row.enrollment_id, identity) != identity:
            raise MLDiagnostic('ENROLLMENT_IDENTITY_MISMATCH')
        predecessor = rows.get(row.supersedes_id)
        if row.revision == 1:
            if row.supersedes_id is not None:
                raise MLDiagnostic('INVALID_REVISION')
        elif predecessor is None or (predecessor.enrollment_id, predecessor.period_id, predecessor.cutoff_at,
                predecessor.data_origin, predecessor.revision + 1) != (row.enrollment_id, row.period_id,
                row.cutoff_at, row.data_origin, row.revision) or predecessor.created_at > row.created_at:
            raise MLDiagnostic('INVALID_REVISION')
        label = labels[row.snapshot_id]
        if label.criterion_version != config.criterion_version or label.outcome_definition != config.criterion_definition:
            raise MLDiagnostic('CRITERION_INCOMPATIBLE')
        if label.provenance == row.input_provenance:
            raise MLDiagnostic('LABEL_MUST_BE_FUTURE_OUTCOME')
        if (label.observed_at.astimezone(LIMA).date() < row.target_date or label.observed_at <= row.cutoff_at
                or label.available_at < label.observed_at or label.available_at > dataset.evaluation_as_of):
            raise MLDiagnostic('LABEL_NOT_OBSERVED_IN_HORIZON')
    return dataset


def frame(rows: list[Observation], config: FeatureConfig) -> pd.DataFrame:
    return pd.DataFrame([{k: np.nan if row.values[k] is None else row.values[k]
                          for k in config.features} for row in rows], columns=list(config.features))
