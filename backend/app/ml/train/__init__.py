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
    common = {'manifest_version':'ml-artifact-v1','dataset_hash':dataset_hash,
        'dataset_schema_version':dataset.schema_version,'feature_schema':config.model_dump(mode='json'),
        'class_order':list(CLASSES),'encoded_classes':[0,1,2],'reference_criterion_version':config.criterion_version,
        'horizon_days':config.horizon_days,'seed':seed,'versions':versions(),'scope':dataset.scope,
        'data_origin':'REAL','provenance':dataset.provenance,'students':len(set(groups)),
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
