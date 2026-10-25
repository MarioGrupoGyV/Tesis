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


def predict_snapshot(snapshot: Observation, model_bundle: ModelBundle | None, *, demo_copy: bool = False) -> PredictionResult:
    """`demo_copy` (ADR 014) solo lo pasa la evaluación de DEMO-VIVO con la copia verificada del SVM REAL activo y el interruptor
    encendido: admite ese artefacto REAL institucional sobre un corte de demostración. Por defecto la regla de origen no cambia."""
    if model_bundle is None:
        return PredictionResult('MODEL_NOT_AVAILABLE','Modelo no disponible')
    if not snapshot.eligible:
        return PredictionResult('INELIGIBLE','NOT_ELIGIBLE')
    try:
        # Origen que el artefacto debe declarar: el del corte; con la copia de demostración, el REAL del artefacto institucional.
        origin = snapshot.data_origin
        if demo_copy:
            if (snapshot.data_origin != 'SYNTHETIC' or model_bundle.manifest['data_origin'] != 'REAL'
                    or (model_bundle.manifest['scope'], model_bundle.manifest['manifest_version']) != ('INSTITUTIONAL_STUDY', 'ml-artifact-v3')):
                raise MLDiagnostic('MODEL_INCOMPATIBLE')
            origin = 'REAL'
        if (model_bundle.manifest['versions'] != versions() or
                model_bundle.manifest['data_origin'] != origin or
                (origin == 'SYNTHETIC' and
                 (model_bundle.manifest['scope'] != 'SYNTHETIC_STUDY' or model_bundle.manifest['manifest_version'] != 'ml-artifact-v2')) or
                (origin == 'REAL' and (model_bundle.manifest['scope'], model_bundle.manifest['manifest_version']) not in
                 (('ISOLATED_TEST', 'ml-artifact-v1'), ('INSTITUTIONAL_STUDY', 'ml-artifact-v3'))) or
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
