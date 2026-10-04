"""Esquema privado y versionado del manifiesto; nunca proyección pública de modelos."""
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
    manifest_version: Literal['ml-artifact-v1']
    dataset_schema_version: Literal['ml-dataset-v1']
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
    scope: Literal['ISOLATED_TEST']
    data_origin: Literal['REAL']
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

    @model_validator(mode='after')
    def consistent(self):
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
