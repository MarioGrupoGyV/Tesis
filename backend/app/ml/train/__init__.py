"""Factories y comparación acotada. No se invoca desde HTTP ni al arrancar."""
from dataclasses import dataclass
import hashlib
import math
from importlib.metadata import version
import platform

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from threadpoolctl import threadpool_limits
from xgboost import XGBClassifier

from app.ml.features import Dataset, FeatureConfig, CLASSES, MLDiagnostic, frame, validate_dataset
from app.ml.evaluate import metrics, partitions

ALGORITHMS = ('DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST')


def public_parameters(value):
    if isinstance(value,dict):
        return {k:public_parameters(v) for k,v in value.items()}
    if isinstance(value,float) and not math.isfinite(value):
        return {'numeric_sentinel':str(value)}
    return value


def versions():
    return {'python':platform.python_version(), **{p:version(p) for p in
            ('scikit-learn','numpy','scipy','pandas','joblib','xgboost-cpu')}}


def factory(algorithm: str, config: FeatureConfig, seed: int) -> Pipeline:
    estimators = {
        'DUMMY':lambda:DummyClassifier(strategy='prior', random_state=seed),
        'RANDOM_FOREST':lambda:RandomForestClassifier(n_estimators=32,max_depth=5,n_jobs=1,random_state=seed),
        'SVM':lambda:SVC(C=1.0,kernel='rbf',probability=False,random_state=seed,cache_size=64,max_iter=10000),
        'XGBOOST':lambda:XGBClassifier(n_estimators=24,max_depth=3,learning_rate=0.1,n_jobs=1,
            device='cpu',tree_method='hist',objective='multi:softprob',num_class=3,random_state=seed),
    }
    if algorithm not in estimators:
        raise MLDiagnostic('UNKNOWN_ALGORITHM')
    numeric = [name for name in config.features if name != 'participation_level']
    steps = [('imputer', SimpleImputer(strategy='median', keep_empty_features=True))]
    if algorithm == 'SVM':
        steps.append(('scale', StandardScaler()))
    categories = Pipeline([('imputer',SimpleImputer(strategy='most_frequent',keep_empty_features=True)),
        ('encode',OneHotEncoder(categories=[config.participation_values],handle_unknown='error',sparse_output=False))])
    preprocessing = ColumnTransformer([('numeric',Pipeline(steps),numeric),
        ('categorical',categories,['participation_level'])],remainder='drop')
    return Pipeline([('features',preprocessing),('estimator',estimators[algorithm]())])


@dataclass
class ModelBundle:
    pipeline: Pipeline
    config: FeatureConfig
    manifest: dict


def compare(dataset: Dataset, seed: int = 1729, requested_folds: int = 5) -> dict[str, ModelBundle]:
    if dataset.scope != 'ISOLATED_TEST':
        from app.services.processing_policy import require_ml_protocol
        require_ml_protocol()
    return _compare(dataset, seed, requested_folds)


def _compare(dataset: Dataset, seed: int, requested_folds: int):
    validate_dataset(dataset)
    if not 2 <= requested_folds <= 5 or not 0 <= seed < 2**32:
        raise MLDiagnostic('INVALID_EVALUATION_CONFIGURATION')
    rows, config = dataset.observations, dataset.config
    labels = {label.snapshot_id:CLASSES.index(label.risk) for label in dataset.labels}
    y = np.array([labels[row.snapshot_id] for row in rows])
    groups = np.array([row.student_key for row in rows])
    splits, strategy = partitions(y, groups, seed, requested_folds)
    x = frame(rows, config)
    dataset_hash = hashlib.sha256(dataset.model_dump_json().encode()).hexdigest()
    synthetic = dataset.scope == 'SYNTHETIC_STUDY'
    common = {'manifest_version':'ml-artifact-v2' if synthetic else 'ml-artifact-v1','dataset_hash':dataset_hash,
        'dataset_schema_version':dataset.schema_version,'feature_schema':config.model_dump(mode='json'),
        'class_order':list(CLASSES),'encoded_classes':[0,1,2],'reference_criterion_version':config.criterion_version,
        'horizon_days':config.horizon_days,'seed':seed,'versions':versions(),'scope':dataset.scope,
        'data_origin':'SYNTHETIC' if synthetic else 'REAL','provenance':dataset.provenance,'students':len(set(groups)),
        'observations':len(rows),'folds_effective':len(splits),'split_strategy':strategy,
        'partitions':[{'train':tr.tolist(),'validation':va.tolist(),
            'train_students':sorted(set(groups[tr])),'validation_students':sorted(set(groups[va]))} for tr,va in splits],
        'probabilities_calibrated':False,'approved':False,
        'limits':['Prueba de software aislada; no resultado institucional ni validación de hipótesis.',
                  'Sin tuning, calibración, selección automática de ganador ni evaluación prospectiva.']}
    bundles = {}
    with threadpool_limits(limits=1):
        for algorithm in ALGORITHMS:
            predictions = np.empty(len(y), dtype=int)
            fold_metrics = []
            for train, validation in splits:
                if x.iloc[train].isna().all().any():
                    raise MLDiagnostic('TRAIN_FEATURE_WITHOUT_SUPPORT')
                pipeline = factory(algorithm, config, seed)
                pipeline.fit(x.iloc[train], y[train])
                predicted = pipeline.predict(x.iloc[validation]).astype(int)
                predictions[validation] = predicted
                fold_metrics.append(metrics(y[validation],predicted))
            pipeline = factory(algorithm,config,seed).fit(x,y)
            manifest = {**common,'algorithm':algorithm,'parameters':public_parameters(pipeline.named_steps['estimator'].get_params()),
                'metrics':metrics(y,predictions),'fold_metrics':fold_metrics,
                'validation_predictions':[{'snapshot_id':str(row.snapshot_id),'expected':CLASSES[int(expected)],
                    'predicted':CLASSES[int(predicted)]} for row,expected,predicted in zip(rows,y,predictions)]}
            bundles[algorithm] = ModelBundle(pipeline,config,manifest)
    return bundles


@dataclass(frozen=True)
class StudyComparison:
    bundles: dict[str, ModelBundle]
    report: dict
    selected_algorithm: str
    training_dataset: Dataset


def compare_study(dataset: Dataset, protocol) -> StudyComparison:
    """CV de desarrollo y reserva temporal externa son evaluaciones separadas.

    Selección precede a lectura/evaluación de etiquetas de la reserva. Se ajustan
    los cuatro pipelines exclusivamente con desarrollo; ningún fit usa la reserva.
    """
    from uuid import NAMESPACE_URL, uuid5
    from decimal import Decimal
    from app.ml.features import LIMA
    from app.ml.synthetic import SyntheticStudyConfig, canonical, digest, instant

    protocol = SyntheticStudyConfig.model_validate(protocol.model_dump())
    validate_dataset(dataset, allow_ineligible=True)
    metadata = dataset.synthetic_protocol or {}
    if (dataset.scope != 'SYNTHETIC_STUDY' or metadata.get('config') != protocol.model_dump(mode='json') or
            dataset.config != protocol.features or metadata.get('generator_version') != protocol.generator_version or
            metadata.get('config_hash') != digest(canonical(protocol.model_dump(mode='json')))):
        raise MLDiagnostic('SYNTHETIC_PROTOCOL_INCOMPATIBLE')
    seed = metadata.get('seed')
    if not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise MLDiagnostic('INVALID_EVALUATION_CONFIGURATION')
    expected_study = str(uuid5(NAMESPACE_URL, f'{protocol.generator_version}:{metadata["config_hash"]}:{seed}'))
    if metadata.get('study_id') != expected_study:
        raise MLDiagnostic('SYNTHETIC_STUDY_ID_INCOMPATIBLE')
    development = set(metadata.get('development_students', []))
    external = set(metadata.get('external_students', []))
    all_students = {row.student_key for row in dataset.observations}
    if (not development or not external or development & external or
            development | external != all_students or len(all_students) != protocol.student_count):
        raise MLDiagnostic('SYNTHETIC_GROUP_PLAN_INCOMPATIBLE')
    labels = {label.snapshot_id: label for label in dataset.labels}
    for label in dataset.labels:
        outcome = label.future_outcome
        if (outcome is None or set(outcome) != {'average_grade', 'attendance_pct', 'activities_pct', 'behavior_incidents'} or
                any(not np.isfinite(value) or not dataset.config.scales[name].minimum <= value <= dataset.config.scales[name].maximum or
                    Decimal(str(value)).normalize().as_tuple().exponent < -dataset.config.scales[name].decimals
                    for name, value in outcome.items()) or protocol.criterion.classify(outcome) != label.risk):
            raise MLDiagnostic('SYNTHETIC_FUTURE_OUTCOME_OR_LABEL_INCOMPATIBLE')
    dev_indices, external_indices = [], []
    exclusions = {}
    fit_at = instant(protocol.fit_date)
    for index, row in enumerate(dataset.observations):
        day = row.cutoff_at.astimezone(LIMA).date()
        reason = None
        if row.student_key in development:
            if day not in protocol.development_cutoffs:
                reason = 'DEVELOPMENT_LATER_CUT_NOT_FOR_FIT'
            elif labels[row.snapshot_id].available_at >= fit_at or row.created_at > fit_at:
                reason = 'DEVELOPMENT_LABEL_OR_OBSERVATION_AFTER_FIT'
            elif not row.eligible:
                reason = 'DEVELOPMENT_NOT_ELIGIBLE'
            else:
                dev_indices.append(index)
        else:
            if day not in protocol.external_cutoffs or row.cutoff_at <= fit_at:
                reason = 'RESERVED_EARLY_CUT_NOT_FOR_EXTERNAL_EVALUATION'
            elif not row.eligible:
                reason = 'EXTERNAL_NOT_ELIGIBLE'
            elif (any(row.values[name] is None for name in protocol.required_features) or
                    sum(v is None for v in row.values.values()) / len(row.values) > protocol.inference_max_missing_fraction):
                reason = 'EXTERNAL_INFERENCE_ABSTENTION'
            else:
                external_indices.append(index)
        if reason:
            exclusions[reason] = exclusions.get(reason, 0) + 1
    if not dev_indices or not external_indices:
        raise MLDiagnostic('INSUFFICIENT_DEVELOPMENT_OR_EXTERNAL_SUPPORT')
    development_rows = [dataset.observations[i] for i in dev_indices]
    training_dataset = dataset.model_copy(update={'evaluation_as_of': fit_at, 'observations': development_rows,
        'labels': [labels[row.snapshot_id] for row in development_rows]})
    bundles = _compare(training_dataset, seed, protocol.requested_folds)
    # Fixed rule declared in protocol; no external prediction/metric exists yet.
    def selection_key(name):
        score = bundles[name].manifest['metrics']
        f1, balanced = score['macro']['f1'], score['balanced_accuracy']
        return (-(f1 if f1 is not None else -1), -(balanced if balanced is not None else -1), ALGORITHMS.index(name))
    selected = min(ALGORITHMS, key=selection_key)
    external_rows = [dataset.observations[i] for i in external_indices]
    if max(labels[row.snapshot_id].available_at for row in development_rows) >= min(row.cutoff_at for row in external_rows):
        raise MLDiagnostic('TRAIN_LABEL_AVAILABLE_AFTER_EXTERNAL_CUTOFF')
    x_external = frame(external_rows, dataset.config)
    y_external = np.array([CLASSES.index(labels[row.snapshot_id].risk) for row in external_rows])
    plan = {'fit_at': fit_at.isoformat(), 'selection_rule': protocol.selection,
        'selected_algorithm': selected, 'development_students': sorted(development), 'external_students': sorted(external),
        'development_source_indices': dev_indices, 'external_source_indices': external_indices,
        'source_observations': len(dataset.observations), 'source_dataset_hash': digest(dataset.model_dump_json().encode()),
        'exclusions': exclusions, 'development_labels_available_max':
            max(labels[row.snapshot_id].available_at for row in development_rows).isoformat(),
        'external_cutoff_min': min(row.cutoff_at for row in external_rows).isoformat()}
    reports = {}
    with threadpool_limits(limits=1):
        for algorithm, bundle in bundles.items():
            predictions = bundle.pipeline.predict(x_external).astype(int)
            external_metrics = metrics(y_external, predictions)
            variation = {}
            for field in ('macro_f1', 'balanced_accuracy'):
                scores = [(fold['macro']['f1'] if field == 'macro_f1' else fold['balanced_accuracy'])
                          for fold in bundle.manifest['fold_metrics']]
                estimable = all(value is not None for value in scores)
                variation[field] = {'mean': float(np.mean(scores)) if estimable else None,
                    'std': float(np.std(scores, ddof=1)) if estimable and len(scores) > 1 else None,
                    'minimum': float(min(scores)) if estimable else None,
                    'maximum': float(max(scores)) if estimable else None,
                    'reason': None if estimable else 'FOLD_METRIC_NOT_ESTIMABLE'}
            bundle.manifest.update({'study_id': expected_study, 'generator_version': protocol.generator_version,
                'synthetic_config_hash': metadata['config_hash'], 'synthetic_evaluation': plan,
                'external_metrics': external_metrics, 'fold_variation': variation,
                'external_predictions': [{'snapshot_id': str(row.snapshot_id), 'expected': CLASSES[int(expected)],
                    'predicted': CLASSES[int(predicted)]} for row, expected, predicted in zip(external_rows, y_external, predictions)],
                'limits': ['SYNTHETIC_STUDY: comparación condicionada por trayectorias y ruido del generador.',
                    'CV por estudiante en desarrollo y reserva externa posterior son evaluaciones distintas.',
                    'Sin evidencia de eficacia, impacto ni generalización a estudiantes reales.',
                    'Sin tuning ni calibración; aprobación técnica permite únicamente simulación.']})
            reports[algorithm] = {'development': bundle.manifest['metrics'], 'external': external_metrics,
                                 'fold_variation': variation}
    report = {'scope': 'SYNTHETIC_STUDY', 'data_origin': 'SYNTHETIC', 'study_id': expected_study,
        'generator_version': protocol.generator_version, 'seed': seed, 'student_count': len(all_students),
        'observation_count': len(dataset.observations), 'development_student_count': len(development),
        'external_student_count': len(external), 'development_observation_count': len(development_rows),
        'external_observation_count': len(external_rows), 'folds_effective': bundles['DUMMY'].manifest['folds_effective'],
        'fit_at': fit_at.isoformat(), 'selection_rule': protocol.selection, 'selected_algorithm': selected,
        'exclusions': exclusions, 'algorithms': reports, 'limits': bundles['DUMMY'].manifest['limits']}
    return StudyComparison(bundles, report, selected, training_dataset)
