"""Esquema privado y versionado del manifiesto; nunca proyección pública de modelos."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.ml.features import CLASSES, FeatureConfig, InternalModel


class Partition(InternalModel):
    train: list[int]
    validation: list[int]
    train_students: list[str]
    validation_students: list[str]

    @model_validator(mode='after')
    def disjoint(self):
        if (not self.train or not self.validation or set(self.train)&set(self.validation)
                or set(self.train_students)&set(self.validation_students)
                or min(self.train+self.validation)<0):
            raise ValueError('INVALID_GROUP_PARTITION')
        return self


class ValidationPrediction(InternalModel):
    snapshot_id: UUID
    expected: Literal['LOW','MEDIUM','HIGH']
    predicted: Literal['LOW','MEDIUM','HIGH']


class ArtifactManifest(InternalModel):
    manifest_version: Literal['ml-artifact-v1', 'ml-artifact-v2']
    dataset_schema_version: Literal['ml-dataset-v1', 'ml-dataset-v2']
    artifact_key: str = Field(pattern=r'^[0-9a-f]{32}$')
    artifact_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    dataset_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    files: dict[str,str]
    feature_schema: FeatureConfig
    class_order: list[str]
    encoded_classes: list[int]
    reference_criterion_version: str
    horizon_days: int = Field(ge=1,le=366)
    seed: int = Field(ge=0,lt=2**32)
    versions: dict[str,str]
    scope: Literal['ISOLATED_TEST', 'SYNTHETIC_STUDY']
    data_origin: Literal['REAL', 'SYNTHETIC']
    provenance: str = Field(min_length=1)
    students: int = Field(ge=2)
    observations: int = Field(ge=2,le=10000)
    folds_effective: int = Field(ge=2,le=5)
    split_strategy: Literal['StratifiedGroupKFold','GroupKFold']
    partitions: list[Partition]
    probabilities_calibrated: Literal[False]
    approved: Literal[False]
    limits: list[str]
    algorithm: Literal['DUMMY','RANDOM_FOREST','SVM','XGBOOST']
    parameters: dict
    metrics: dict
    fold_metrics: list[dict]
    validation_predictions: list[ValidationPrediction]
    study_id: UUID | None = None
    generator_version: Literal['synthetic-generator-v1'] | None = None
    synthetic_config_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    synthetic_evaluation: dict | None = None
    external_metrics: dict | None = None
    fold_variation: dict | None = None
    external_predictions: list[ValidationPrediction] | None = None

    @model_validator(mode='after')
    def consistent(self):
        synthetic = self.scope == 'SYNTHETIC_STUDY'
        if (self.data_origin != ('SYNTHETIC' if synthetic else 'REAL') or
                self.manifest_version != ('ml-artifact-v2' if synthetic else 'ml-artifact-v1') or
                self.dataset_schema_version != ('ml-dataset-v2' if synthetic else 'ml-dataset-v1')):
            raise ValueError('MANIFEST_SCOPE_ORIGIN_INCOMPATIBLE')
        synthetic_fields = [self.study_id, self.generator_version, self.synthetic_config_hash,
            self.synthetic_evaluation, self.external_metrics, self.fold_variation, self.external_predictions]
        if (synthetic and any(value is None for value in synthetic_fields) or
                not synthetic and any(value is not None for value in synthetic_fields)):
            raise ValueError('SYNTHETIC_MANIFEST_METADATA_REQUIRED')
        if synthetic:
            plan = self.synthetic_evaluation
            try:
                development, external = set(plan['development_students']), set(plan['external_students'])
                dev_indices, external_indices = plan['development_source_indices'], plan['external_source_indices']
                if (not development or not external or development & external or not external_indices or
                        len(dev_indices) != self.observations or len(set(dev_indices)) != len(dev_indices) or
                        len(set(external_indices)) != len(external_indices) or set(dev_indices) & set(external_indices) or
                        len(self.external_predictions) != len(external_indices) or
                        any(index < 0 or index >= plan['source_observations'] for index in dev_indices + external_indices) or
                        datetime.fromisoformat(plan['development_labels_available_max']) >= datetime.fromisoformat(plan['fit_at']) or
                        datetime.fromisoformat(plan['fit_at']) >= datetime.fromisoformat(plan['external_cutoff_min']) or
                        plan['selection_rule'] != 'DEV_MACRO_F1_THEN_BALANCED_ACCURACY_THEN_FIXED_ORDER' or
                        plan['selected_algorithm'] not in ('DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST')):
                    raise ValueError('INVALID_SYNTHETIC_HOLDOUT')
            except (KeyError, TypeError):
                raise ValueError('INVALID_SYNTHETIC_HOLDOUT') from None
        if self.class_order != list(CLASSES) or self.encoded_classes != [0,1,2]:
            raise ValueError('UNEXPECTED_MODEL_CLASSES')
        if (len(self.partitions)!=self.folds_effective or len(self.fold_metrics)!=self.folds_effective
                or len(self.validation_predictions)!=self.observations or self.students>self.observations):
            raise ValueError('INVALID_EVALUATION_COUNTS')
        validation=[i for split in self.partitions for i in split.validation]
        if sorted(validation)!=list(range(self.observations)):
            raise ValueError('INVALID_VALIDATION_COVERAGE')
        for split in self.partitions:
            if sorted(split.train+split.validation)!=list(range(self.observations)):
                raise ValueError('INVALID_TRAIN_COVERAGE')
        return self
