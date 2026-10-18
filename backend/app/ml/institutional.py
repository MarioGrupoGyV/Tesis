"""Comparación institucional (ADR 012 §9): validación cruzada agrupada por estudiante, repetida, con n pequeño.

Unidad = estudiante (B1 y B2 del mismo estudiante siempre juntos). Las etiquetas vienen del dataset (construido desde
`risk_references`), nunca de las características. Resultados exploratorios: no demuestran eficacia escolar ni validan la tesis.
"""
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


@dataclass(frozen=True)
class InstitutionalComparison:
    bundles: dict
    report: dict
    selected_algorithm: str
    training_dataset: Dataset


def selection_key(summaries):
    def key(name):
        f1, balanced = summaries[name]['macro']['f1']['mean'], summaries[name]['balanced_accuracy']['mean']
        return (-(f1 if f1 is not None else -1), -(balanced if balanced is not None else -1), ALGORITHMS.index(name))
    return key


def compare_institutional(dataset: Dataset, *, seed: int, study_id, repetitions: int = DEFAULT_REPETITIONS,
                          requested_folds: int = 5, leave_one_student_out: bool = False) -> InstitutionalComparison:
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
    first = {}
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
                pooled[algorithm] += np.array(score['confusion_matrix'])
                if repetition == 0:
                    first[algorithm] = (predictions, fold_scores)
        summaries = {name: summarize(per_repetition[name], pooled[name]) for name in ALGORITHMS}
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
            reports[algorithm] = {'repeated_cv': summaries[algorithm],
                                  **({'leave_one_student_out': sensitivity[algorithm]} if sensitivity else {})}
    report = {'scope': 'INSTITUTIONAL_STUDY', 'data_origin': 'REAL', 'study_id': str(study_id), 'seed': seed,
        'students': students, 'observations': len(rows), 'support_by_class': support, 'repetitions': repetitions,
        'requested_folds': requested_folds, 'selection_rule': SELECTION_RULE, 'selected_algorithm': selected,
        'warnings': notes, 'approval_kind': APPROVAL_KIND, 'algorithms': reports, 'source_dataset_hash': dataset_hash}
    report['report_sha256'] = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return InstitutionalComparison(bundles, report, selected, dataset)
