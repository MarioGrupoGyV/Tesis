"""Inferencia tipada sin probabilidades no calibradas ni riesgo inventado."""
from dataclasses import dataclass
from typing import Literal
from app.ml.features import CLASSES, MLDiagnostic, Observation, frame, validate_observation
from app.ml.train import ModelBundle, versions


@dataclass(frozen=True)
class PredictionResult:
    status: Literal['EVALUATED','MODEL_NOT_AVAILABLE','INSUFFICIENT_DATA','INELIGIBLE','INCOMPATIBLE']
    reason: str | None = None
    risk_level: Literal['LOW','MEDIUM','HIGH'] | None = None
    probabilities_calibrated: bool = False
    probability_low: None = None
    probability_medium: None = None
    probability_high: None = None


def class_mapping(classes):
    values = list(classes)
    if len(values) != 3 or set(values) != {0,1,2}:
        raise MLDiagnostic('UNEXPECTED_MODEL_CLASSES')
    return {int(value):CLASSES[int(value)] for value in values}


def predict_snapshot(snapshot: Observation, model_bundle: ModelBundle | None) -> PredictionResult:
    if model_bundle is None:
        return PredictionResult('MODEL_NOT_AVAILABLE','Modelo no disponible')
    if not snapshot.eligible:
        return PredictionResult('INELIGIBLE','NOT_ELIGIBLE')
    try:
        if (model_bundle.manifest['versions'] != versions() or
                model_bundle.manifest['data_origin'] != snapshot.data_origin or
                model_bundle.manifest['feature_schema'] != model_bundle.config.model_dump(mode='json') or
                model_bundle.manifest['probabilities_calibrated'] is not False):
            raise MLDiagnostic('MODEL_INCOMPATIBLE')
        validate_observation(snapshot,model_bundle.config)
        mapping = class_mapping(model_bundle.pipeline.classes_)
        values = snapshot.values
        if (any(values[name] is None for name in model_bundle.config.required_features) or
                sum(v is None for v in values.values()) / len(values) > model_bundle.config.inference_max_missing_fraction):
            return PredictionResult('INSUFFICIENT_DATA','Datos insuficientes')
        predicted = model_bundle.pipeline.predict(frame([snapshot], model_bundle.config))[0]
        return PredictionResult('EVALUATED',risk_level=mapping[predicted])
    except (MLDiagnostic, ValueError, KeyError):
        return PredictionResult('INCOMPATIBLE','MODEL_OR_SNAPSHOT_INCOMPATIBLE')
