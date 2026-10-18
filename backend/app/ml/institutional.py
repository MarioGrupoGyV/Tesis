"""Comparación institucional (ADR 012 §9): validación cruzada agrupada por estudiante, repetida, con n pequeño.

Unidad = estudiante (B1 y B2 del mismo estudiante siempre juntos). Las etiquetas vienen del dataset (construido desde
`risk_references`), nunca de las características. Resultados exploratorios: no demuestran eficacia escolar ni validan la tesis.
"""
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

import numpy as np
from sklearn.model_selection import LeaveOneGroupOut
from threadpoolctl import threadpool_limits

from app.ml.evaluate import metrics, partitions
from app.ml.features import CLASSES, MLDiagnostic, Dataset, FeatureConfig, frame, validate_dataset
from app.ml.train import ALGORITHMS, ModelBundle, factory, public_parameters, versions

DEFAULT_REPETITIONS = 20
MIN_REPETITIONS = 20
SELECTION_RULE = 'REPEATED_CV_MACRO_F1_THEN_BALANCED_ACCURACY_THEN_FIXED_ORDER'
APPROVAL_KIND = 'LOCAL_EXPLORATORY'
SEED_STRIDE = 7919


def derive_seeds(seed: int, repetitions: int) -> list[int]:
    return [(seed + SEED_STRIDE * index) % 2**32 for index in range(repetitions)]


def warnings_for(students: int, observations: int, support: dict) -> list[str]:
    smallest = min(item['students'] for item in support.values())
    notes = [
        f'n = {students} estudiantes ({observations} observaciones no independientes: un mismo estudiante aporta varios bimestres).',
        'Sin validación externa ni prospectiva: no hay reserva independiente con estudiantes distintos.',
        'La selección del algoritmo y su evaluación usan los mismos datos (posible optimismo); se reportan los cuatro algoritmos.',
        f'Clase con menos estudiantes: {smallest}. Las métricas por clase con pocos casos son inestables.',
        'La dispersión entre repeticiones no es un intervalo de confianza.',
        'Probabilidades no calibradas. Resultados exploratorios sobre datos reales locales: no demuestran eficacia escolar ni validan la tesis.']
    if smallest < 10:
        notes.append('Alguna clase tiene menos de 10 estudiantes: las métricas de esa clase no son estimables con fiabilidad.')
    return notes


def spread(values):
    values = list(values)
    if not values or any(value is None for value in values):
        return {'mean': None, 'sd': None, 'minimum': None, 'maximum': None, 'reason': 'REPETITION_METRIC_NOT_ESTIMABLE'}
    array = np.asarray(values, dtype=float)
    return {'mean': float(array.mean()), 'sd': float(array.std(ddof=1)) if len(array) > 1 else None,
            'minimum': float(array.min()), 'maximum': float(array.max()), 'reason': None}


def cohen_kappa(confusion) -> float | None:
    """Kappa de Cohen de una matriz de confusión (filas = referencia, columnas = predicho); null si no es estimable."""
    matrix = np.asarray(confusion, dtype=float)
    total = matrix.sum()
    if not total:
        return None
    observed = np.trace(matrix) / total
    expected = float((matrix.sum(axis=1) * matrix.sum(axis=0)).sum()) / total ** 2
    return None if expected == 1 else float((observed - expected) / (1 - expected))


def summarize(repetition_metrics: list[dict], matrix: np.ndarray) -> dict:
    per_class = {}
    for name in CLASSES:
        per_class[name] = {key: spread(item['per_class'][name][key] for item in repetition_metrics)
                           for key in ('precision', 'recall', 'f1')}
        per_class[name]['support_per_repetition'] = int(repetition_metrics[0]['per_class'][name]['support'])
    return {'repetitions': len(repetition_metrics),
            'macro': {key: spread(item['macro'][key] for item in repetition_metrics) for key in ('precision', 'recall', 'f1')},
            'accuracy': spread(item['accuracy'] for item in repetition_metrics),
            'balanced_accuracy': spread(item['balanced_accuracy'] for item in repetition_metrics),
            'cohen_kappa': spread(cohen_kappa(item['confusion_matrix']) for item in repetition_metrics),
            'per_class': per_class, 'aggregated_confusion_matrix': matrix.tolist(), 'class_order': list(CLASSES)}


def flat_metrics(summary: dict) -> dict:
    """Forma plana (medias) compatible con quien lee `metrics['macro']['f1']`; la dispersión queda en `repeated_cv`."""
    return {'class_order': list(CLASSES), 'confusion_matrix': summary['aggregated_confusion_matrix'],
            'macro': {key: summary['macro'][key]['mean'] for key in ('precision', 'recall', 'f1')},
            'accuracy': summary['accuracy']['mean'], 'balanced_accuracy': summary['balanced_accuracy']['mean'],
            'per_class': {name: {key: summary['per_class'][name][key]['mean'] for key in ('precision', 'recall', 'f1')}
                          | {'support': summary['per_class'][name]['support_per_repetition']} for name in CLASSES},
            'auc': None, 'repeated_cv': summary,
            'limitations': ['Medias de repeticiones de validación cruzada agrupada; null = no estimable. Sin calibración.']}


DETECTION_DEFINITION = 'OUT_OF_FOLD_MEDIUM_OR_HIGH_V1'
DETECTION_NOTE = ('Detección = observaciones de riesgo de referencia Medio o Alto que el modelo marcó Medio o Alto cuando ese estudiante estaba en el '
                  'pliegue de validación (nunca en entrenamiento). Un modelo que marcara a todos como Alto detectaría el 100 %: se informa también la '
                  'falsa alarma (Bajo marcado Medio/Alto).')


def bimester_codes(rows, bimesters) -> list[str]:
    """Código de bimestre de cada observación: por fecha objetivo (cierre) del protocolo; sin protocolo, B1, B2… por orden de fecha."""
    if bimesters is None:
        ordered = sorted({row.target_date for row in rows})
        bimesters = {day: f'B{index + 1}' for index, day in enumerate(ordered)}
    try:
        return [bimesters[row.target_date] for row in rows]
    except KeyError:
        raise MLDiagnostic('BIMESTER_NOT_MAPPED') from None


def detection_counts(y: np.ndarray, predicted: np.ndarray, mask: np.ndarray) -> dict:
    """Conteos de una repetición. Clases codificadas 0 = Bajo, 1 = Medio, 2 = Alto; «marcado» = predicho Medio o Alto."""
    reference, flagged = y[mask], predicted[mask] >= 1
    low, medium, high = reference == 0, reference == 1, reference == 2
    return {'reference_low': int(low.sum()), 'reference_medium': int(medium.sum()), 'reference_high': int(high.sum()),
            'low_flagged': int((low & flagged).sum()), 'medium_flagged': int((medium & flagged).sum()),
            'high_flagged': int((high & flagged).sum()), 'high_as_low': int((high & ~flagged).sum())}


def ratio(numerator: int, denominator: int):
    return numerator / denominator if denominator else None


def detection_rates(counts: dict) -> dict:
    at_risk = counts['reference_medium'] + counts['reference_high']
    return {'detection': ratio(counts['medium_flagged'] + counts['high_flagged'], at_risk),
            'medium_detected': ratio(counts['medium_flagged'], counts['reference_medium']),
            'high_detected': ratio(counts['high_flagged'], counts['reference_high']),
            'high_as_low': ratio(counts['high_as_low'], counts['reference_high']),
            'low_flagged': ratio(counts['low_flagged'], counts['reference_low'])}


def detection_summary(per_repetition: list[dict]) -> dict:
    """Media y desviación entre repeticiones de cada tasa, más los conteos sumados de todas las repeticiones (transparencia)."""
    rates = [detection_rates(counts) for counts in per_repetition]
    pooled = {key: sum(counts[key] for counts in per_repetition) for key in per_repetition[0]}
    pooled['reference_at_risk'] = pooled['reference_medium'] + pooled['reference_high']
    pooled['detected'] = pooled['medium_flagged'] + pooled['high_flagged']
    return {'repetitions': len(per_repetition),
            'reference_at_risk_per_repetition': per_repetition[0]['reference_medium'] + per_repetition[0]['reference_high'],
            **{key: spread(rate[key] for rate in rates) for key in rates[0]}, 'pooled': pooled}


def detection_report(per_repetition: list[dict], matrix: np.ndarray) -> dict:
    """Informe de detección fuera de muestra de un algoritmo. `per_repetition[i]` = {'TOTAL': conteos, 'B1': conteos, …}."""
    scopes = list(per_repetition[0])
    summaries = {scope: detection_summary([item[scope] for item in per_repetition]) for scope in scopes}
    # Control cruzado: la suma de las repeticiones debe coincidir con la matriz agregada de la validación cruzada.
    flagged = int(matrix[1][1] + matrix[1][2] + matrix[2][1] + matrix[2][2])
    if summaries['TOTAL']['pooled']['detected'] != flagged or summaries['TOTAL']['pooled']['reference_at_risk'] != int(matrix[1].sum() + matrix[2].sum()):
        raise MLDiagnostic('DETECTION_MATRIX_MISMATCH')
    return {'definition': DETECTION_DEFINITION, 'metric_basis': 'OUT_OF_FOLD', 'note': DETECTION_NOTE, 'total': summaries['TOTAL'],
            'by_bimester': {scope: summaries[scope] for scope in scopes if scope != 'TOTAL'}}


@dataclass(frozen=True)
class InstitutionalComparison:
    bundles: dict
    report: dict
    selected_algorithm: str
    training_dataset: Dataset


@dataclass(frozen=True, eq=False)
class RepetitionRecord:
    """Lo que ya calcula una repetición de un algoritmo, entregado a un colector opcional (exportación para SPSS, Bloque 7).

    `predictions[i]` y `reference[i]` corresponden a `keys[i]` = (código del estudiante, corte) y a `bimesters[i]`, en el orden canónico de la
    comparación (el mismo de `InstitutionalComparison.training_dataset.observations`). Clases 0 = Bajo, 1 = Medio, 2 = Alto. Son copias:
    el colector no puede alterar los resultados de la comparación.
    """
    repetition: int                      # base 0
    seed: int
    algorithm: str
    metrics: dict                        # la misma salida de `metrics()` que alimenta `per_repetition`
    kappa: float | None                  # `cohen_kappa` de la matriz de confusión de esta repetición
    detection: dict                      # {'TOTAL': conteos, 'B1': conteos, …} (igual que `detection_per_repetition`)
    predictions: np.ndarray
    reference: np.ndarray
    keys: tuple
    bimesters: tuple


def selection_key(summaries):
    def key(name):
        f1, balanced = summaries[name]['macro']['f1']['mean'], summaries[name]['balanced_accuracy']['mean']
        return (-(f1 if f1 is not None else -1), -(balanced if balanced is not None else -1), ALGORITHMS.index(name))
    return key


def compare_institutional(dataset: Dataset, *, seed: int, study_id, repetitions: int = DEFAULT_REPETITIONS,
                          requested_folds: int = 5, leave_one_student_out: bool = False, bimesters=None,
                          collector: Callable[[RepetitionRecord], None] | None = None) -> InstitutionalComparison:
    """`collector` (opcional) recibe un `RepetitionRecord` por repetición y algoritmo; no cambia semillas, particiones ni resultados."""
    if dataset.scope != 'INSTITUTIONAL':
        raise MLDiagnostic('INSTITUTIONAL_SCOPE_REQUIRED')
    if not 0 <= seed < 2**32 or not 2 <= requested_folds <= 5 or repetitions < MIN_REPETITIONS:
        raise MLDiagnostic('INVALID_EVALUATION_CONFIGURATION')
    validate_dataset(dataset)
    # Orden canónico (estudiante, corte): la comparación no depende del orden de las filas ni de identificadores internos.
    dataset = dataset.model_copy(update={'observations': sorted(dataset.observations, key=lambda row: (row.student_key, row.cutoff_at))})
    rows, config = dataset.observations, dataset.config
    labels = {label.snapshot_id: CLASSES.index(label.risk) for label in dataset.labels}
    y = np.array([labels[row.snapshot_id] for row in rows])
    groups = np.array([row.student_key for row in rows])
    x = frame(rows, config)
    students = len(set(groups))
    support = {name: {'observations': int((y == index).sum()), 'students': len(set(groups[y == index]))}
               for index, name in enumerate(CLASSES)}
    if any(item['students'] < 2 for item in support.values()):
        raise MLDiagnostic('INSUFFICIENT_CLASS_GROUP_SUPPORT')
    dataset_hash = hashlib.sha256(dataset.model_dump_json().encode()).hexdigest()
    seeds = derive_seeds(seed, repetitions)
    plans = [partitions(y, groups, value, requested_folds) for value in seeds]
    notes = warnings_for(students, len(rows), support)
    pooled = {name: np.zeros((3, 3), dtype=int) for name in ALGORITHMS}
    per_repetition = {name: [] for name in ALGORITHMS}
    codes = bimester_codes(rows, bimesters)
    scopes = {'TOTAL': np.ones(len(y), dtype=bool), **{code: np.array([item == code for item in codes]) for code in sorted(set(codes))}}
    detection_per_repetition = {name: [] for name in ALGORITHMS}
    first = {}
    collected_keys, collected_codes = tuple((row.student_key, row.cutoff_at) for row in rows), tuple(codes)
    with threadpool_limits(limits=1):
        for repetition, (splits, strategy) in enumerate(plans):
            for algorithm in ALGORITHMS:
                predictions = np.empty(len(y), dtype=int)
                fold_scores = []
                for train, validation in splits:
                    if x.iloc[train].isna().all().any():
                        raise MLDiagnostic('TRAIN_FEATURE_WITHOUT_SUPPORT')
                    pipeline = factory(algorithm, config, seeds[repetition]).fit(x.iloc[train], y[train])
                    predicted = pipeline.predict(x.iloc[validation]).astype(int)
                    predictions[validation] = predicted
                    fold_scores.append(metrics(y[validation], predicted))
                score = metrics(y, predictions)
                per_repetition[algorithm].append(score)
                # Solo predicciones de validación: cada observación se predice una vez por repetición, con el estudiante fuera del entrenamiento.
                detection_per_repetition[algorithm].append({scope: detection_counts(y, predictions, mask) for scope, mask in scopes.items()})
                pooled[algorithm] += np.array(score['confusion_matrix'])
                if collector is not None:
                    collector(RepetitionRecord(repetition=repetition, seed=seeds[repetition], algorithm=algorithm, metrics=deepcopy(score),
                        kappa=cohen_kappa(score['confusion_matrix']), detection=deepcopy(detection_per_repetition[algorithm][-1]),
                        predictions=predictions.copy(), reference=y.copy(), keys=collected_keys, bimesters=collected_codes))
                if repetition == 0:
                    first[algorithm] = (predictions, fold_scores)
        summaries = {name: summarize(per_repetition[name], pooled[name]) for name in ALGORITHMS}
        detections = {name: detection_report(detection_per_repetition[name], pooled[name]) for name in ALGORITHMS}
        sensitivity = {}
        if leave_one_student_out:
            for algorithm in ALGORITHMS:
                predictions = np.empty(len(y), dtype=int)
                for train, validation in LeaveOneGroupOut().split(x, y, groups):
                    pipeline = factory(algorithm, config, seed).fit(x.iloc[train], y[train])
                    predictions[validation] = pipeline.predict(x.iloc[validation]).astype(int)
                sensitivity[algorithm] = metrics(y, predictions)
        selected = min(ALGORITHMS, key=selection_key(summaries))
        splits0, strategy0 = plans[0]
        partitions0 = [{'train': tr.tolist(), 'validation': va.tolist(), 'train_students': sorted(set(groups[tr])),
                        'validation_students': sorted(set(groups[va]))} for tr, va in splits0]
        evaluation = {'scope': 'INSTITUTIONAL_STUDY', 'selection_rule': SELECTION_RULE, 'selected_algorithm': selected,
            'repetitions': repetitions, 'requested_folds': requested_folds,
            'effective_folds_per_repetition': [len(split) for split, _ in plans],
            'split_strategies': sorted({strategy for _, strategy in plans}), 'seeds': seeds, 'base_seed': seed,
            'students': students, 'observations': len(rows), 'support_by_class': support,
            'leave_one_student_out': leave_one_student_out, 'warnings': notes, 'approval_kind': APPROVAL_KIND,
            'source_dataset_hash': dataset_hash}
        common = {'manifest_version': 'ml-artifact-v3', 'dataset_hash': dataset_hash, 'dataset_schema_version': dataset.schema_version,
            'feature_schema': config.model_dump(mode='json'), 'class_order': list(CLASSES), 'encoded_classes': [0, 1, 2],
            'reference_criterion_version': config.criterion_version, 'horizon_days': config.horizon_days, 'seed': seed,
            'versions': versions(), 'scope': 'INSTITUTIONAL_STUDY', 'data_origin': 'REAL', 'provenance': dataset.provenance,
            'students': students, 'observations': len(rows), 'folds_effective': len(splits0), 'split_strategy': strategy0,
            'partitions': partitions0, 'probabilities_calibrated': False, 'approved': False,
            'limits': notes + ['Aprobación local exploratoria (LOCAL_EXPLORATORY): no es validación institucional.'],
            'study_id': str(study_id), 'generator_version': 'institutional-loader-v1', 'institutional_evaluation': evaluation}
        bundles, reports = {}, {}
        for algorithm in ALGORITHMS:
            predictions0, fold_scores0 = first[algorithm]
            pipeline = factory(algorithm, config, seed).fit(x, y)
            manifest = {**common, 'algorithm': algorithm,
                'parameters': public_parameters(pipeline.named_steps['estimator'].get_params()),
                'metrics': flat_metrics(summaries[algorithm]), 'fold_metrics': fold_scores0,
                'validation_predictions': [{'snapshot_id': str(row.snapshot_id), 'expected': CLASSES[int(expected)],
                    'predicted': CLASSES[int(predicted)]} for row, expected, predicted in zip(rows, y, predictions0)]}
            bundles[algorithm] = ModelBundle(pipeline, config, manifest)
            # `detection` vive solo en el informe (no en `repeated_cv` ni en el manifiesto del artefacto): las métricas ya publicadas no cambian.
            reports[algorithm] = {'repeated_cv': summaries[algorithm], 'detection': detections[algorithm],
                                  **({'leave_one_student_out': sensitivity[algorithm]} if sensitivity else {})}
    report = {'scope': 'INSTITUTIONAL_STUDY', 'data_origin': 'REAL', 'study_id': str(study_id), 'seed': seed,
        'students': students, 'observations': len(rows), 'support_by_class': support, 'repetitions': repetitions,
        'requested_folds': requested_folds, 'selection_rule': SELECTION_RULE, 'selected_algorithm': selected,
        'warnings': notes, 'approval_kind': APPROVAL_KIND, 'algorithms': reports, 'source_dataset_hash': dataset_hash}
    report['report_sha256'] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return InstitutionalComparison(bundles, report, selected, dataset)
