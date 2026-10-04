"""Fixtures mínimos SOLO pytest; métricas de software, no una población escolar."""
from datetime import UTC, date, datetime, timedelta
import hashlib
import hmac
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
from pydantic import ValidationError

from app.ml.features import (BASE_FEATURES, CLASSES, Dataset, FeatureConfig, Label, MLDiagnostic,
                             Observation, Scale, frame, validate_dataset)
from app.ml.train import ALGORITHMS, compare, factory
from app.ml.evaluate import metrics, partitions
from app.ml.predict import class_mapping, predict_snapshot
from app.ml.artifacts import ArtifactStore, canonical


@pytest.fixture(scope='module')
def ml_dataset():
    config = FeatureConfig(criterion_version='test-outcome-v1',criterion_definition='Independent future fixture outcome',
        horizon_days=1,inference_max_missing_fraction=0.4,required_features=['average_grade'],
        participation_values=[1,2,3],scales={
            name:Scale(minimum=lo,maximum=hi,decimals=precision,unit='isolated fixture only')
            for name,lo,hi,precision in [('average_grade',0,20,2),('attendance_pct',0,100,2),
                ('activities_pct',0,100,2),('participation_level',1,3,0),('behavior_incidents',0,50,0)]})
    observations,labels = [],[]
    period = uuid4()
    # Nueve grupos, dos observaciones por grupo. Etiquetas explícitas futuras,
    # independientes de la fórmula de valores de entrada; no optimizadas por métricas.
    risks = ['LOW','MEDIUM','HIGH','HIGH','LOW','MEDIUM','MEDIUM','HIGH','LOW']
    for student,risk in enumerate(risks):
        enrollment = uuid4()
        for offset in (0,7):
            cutoff = datetime(2026,5,2,4,30,tzinfo=UTC)+timedelta(days=offset)
            row = Observation(student_key=f'isolated-{student}',snapshot_id=uuid4(),enrollment_id=enrollment,
                period_id=period,data_origin='REAL',revision=1,window_start=date(2026,4,1),
                cutoff_at=cutoff,available_at=cutoff-timedelta(hours=4),created_at=cutoff,
                target_date=date(2026,5,2)+timedelta(days=offset),eligible=True,
                input_provenance='isolated-input-fixture',values=dict(zip(BASE_FEATURES,
                    [float(8+student),float(65+student),None if student==0 else float(50+offset),float(1+student%3),float(student%4)])),
                feature_available_at={f:cutoff-timedelta(hours=4) for f in BASE_FEATURES})
            observations.append(row)
            labels.append(Label(snapshot_id=row.snapshot_id,risk=risk,criterion_version=config.criterion_version,
                outcome_definition=config.criterion_definition,provenance='isolated-independent-outcome-fixture',
                observed_at=cutoff+timedelta(days=1),available_at=cutoff+timedelta(days=2)))
    return Dataset(scope='ISOLATED_TEST',provenance='pytest fixture; no institutional data',
        evaluation_as_of=datetime(2026,6,1,tzinfo=UTC),config=config,observations=observations,labels=labels)


@pytest.fixture(scope='module')
def bundles(ml_dataset):
    return compare(ml_dataset)


def test_four_algorithms_and_private_validation(bundles,ml_dataset,tmp_path):
    assert set(bundles)==set(ALGORITHMS)
    common = bundles['DUMMY'].manifest['partitions']
    for algorithm,bundle in bundles.items():
        manifest = bundle.manifest
        assert manifest['folds_effective']==3 and manifest['students']==9 and manifest['observations']==18
        assert manifest['partitions']==common
        assert manifest['metrics']['class_order']==list(CLASSES)
        assert sum(sum(r) for r in manifest['metrics']['confusion_matrix'])==18
        assert len(manifest['validation_predictions'])==18
        assert not manifest['approved'] and not manifest['probabilities_calibrated']
        for split in manifest['partitions']:
            assert not set(split['train_students']) & set(split['validation_students'])
        result = predict_snapshot(ml_dataset.observations[2],bundle)
        assert result.status=='EVALUATED' and result.risk_level in CLASSES
        assert result.probability_low is None and not result.probabilities_calibrated
        store = ArtifactStore(tmp_path/algorithm)
        key = store.save(bundle,ml_dataset)
        restored = store.load(key)
        assert predict_snapshot(ml_dataset.observations[2],restored)==result
        assert (tmp_path/algorithm/key/'estimator.ubj').exists()==(algorithm=='XGBOOST')
    # Solo resumen público, sin identidades, particiones, manifiestos o datasets privados.
    directory = Path('/evidence') if Path('/evidence').exists() else tmp_path
    prefix = os.environ.get('TEST_REPORT_NAME', 's3-local-backend').removesuffix('-backend')
    (directory / (prefix + '-ml-summary.json')).write_text(json.dumps({
        'status':'COMPROBADO','scope':'ISOLATED_SOFTWARE_TEST_ONLY','algorithms':list(bundles),
        'students':9,'observations':18,'folds_effective':3,'seed':1729,
        'versions':bundles['DUMMY'].manifest['versions'],'round_trip_all_algorithms':True,
        'metrics_are_not_school_or_thesis_results':True},indent=2)+'\n')


def test_reproducible_group_partitions():
    y=np.repeat([0,1,2],6); groups=np.repeat(np.arange(9),2)
    a,strategy=partitions(y,groups,7)
    b,_=partitions(y,groups,7)
    assert len(a)==3
    assert all(np.array_equal(x,u) and np.array_equal(z,v) for (x,z),(u,v) in zip(a,b))
    assert all(not set(groups[tr]) & set(groups[va]) for tr,va in a)
    with pytest.raises(MLDiagnostic,match='SUPPORT'):
        partitions([0,0,1,2],['one','one','two','three'],7)


def test_transformations_fit_train_only_and_svm_no_probability(ml_dataset):
    rows=ml_dataset.observations[2:]
    x=frame(rows,ml_dataset.config)
    y=np.resize([0,1,2],len(x))
    x.loc[0,'average_grade']=np.nan
    training=x.iloc[:12].copy(); validation=x.iloc[12:].copy()
    validation.loc[:,'average_grade']=100000
    pipeline=factory('SVM',ml_dataset.config,1).fit(training,y[:12])
    numeric=pipeline.named_steps['features'].named_transformers_['numeric']
    assert numeric.named_steps['imputer'].statistics_[0]==np.nanmedian(training['average_grade'])
    before=numeric.named_steps['scale'].mean_.copy()
    pipeline.predict(validation)
    assert np.array_equal(before,numeric.named_steps['scale'].mean_)
    assert not pipeline.named_steps['estimator'].probability
    assert list(pipeline.feature_names_in_)==list(BASE_FEATURES)
    assert not set(('student_key','target_date','risk','grade','age_years')) & set(pipeline.feature_names_in_)


@pytest.mark.parametrize('field,change,code',[
    ('available_at',lambda r:r.cutoff_at+timedelta(seconds=1),'TEMPORAL'),
    ('target_date',lambda r:date(2026,5,1),'TEMPORAL'),
    ('created_at',lambda r:datetime(2027,1,1,tzinfo=UTC),'NOT_AVAILABLE'),
    ('revision',lambda r:2,'REVISION'),
    ('supersedes_id',lambda r:uuid4(),'REVISION'),
    ('eligible',lambda r:False,'ELIGIBLE'),
    ('values',lambda r:{**r.values,'average_grade':21},'OUT_OF_SCALE'),
    ('values',lambda r:{**r.values,'average_grade':1.123},'PRECISION'),
    ('values',lambda r:{**r.values,'tutor':1},'FEATURE_SCHEMA'),
    ('feature_available_at',lambda r:{**r.feature_available_at,'attendance_pct':r.cutoff_at+timedelta(seconds=1)},'AVAILABLE_AFTER'),
])
def test_invalid_observations(ml_dataset,field,change,code):
    dataset=ml_dataset.model_copy(deep=True)
    setattr(dataset.observations[0],field,change(dataset.observations[0]))
    with pytest.raises(MLDiagnostic,match=code): validate_dataset(dataset)


@pytest.mark.parametrize('kind',['missing','duplicate','same_source','before_target','unavailable','criterion','duplicate_row','wrong_student'])
def test_labels_and_duplicates_rejected(ml_dataset,kind):
    data=ml_dataset.model_copy(deep=True)
    if kind=='missing': data.labels.pop()
    if kind=='duplicate': data.labels.append(data.labels[0])
    if kind=='same_source': data.labels[0].provenance=data.observations[0].input_provenance
    if kind=='before_target': data.labels[0].observed_at=data.observations[0].cutoff_at
    if kind=='unavailable': data.labels[0].available_at=data.evaluation_as_of+timedelta(seconds=1)
    if kind=='criterion': data.labels[0].criterion_version='different'
    if kind=='duplicate_row': data.observations.append(data.observations[0])
    if kind=='wrong_student': data.observations[1].student_key='another-person'
    with pytest.raises(MLDiagnostic): validate_dataset(data)


def test_revision_chain_and_lima(ml_dataset):
    data=ml_dataset.model_copy(deep=True)
    row=data.observations[0].model_copy(deep=True)
    row.snapshot_id=uuid4(); row.revision=2; row.supersedes_id=data.observations[0].snapshot_id
    row.created_at+=timedelta(hours=1)
    label=data.labels[0].model_copy(update={'snapshot_id':row.snapshot_id})
    data.observations.append(row); data.labels.append(label)
    validate_dataset(data)  # Corte UTC mayo 2 = día Lima mayo 1; objetivo mayo 2 válido.
    row.period_id=uuid4()
    with pytest.raises(MLDiagnostic): validate_dataset(data)


def test_incomplete_scales_and_optional_features(ml_dataset):
    config=ml_dataset.config.model_dump()
    config.pop('inference_max_missing_fraction')
    with pytest.raises(ValidationError): FeatureConfig.model_validate(config)
    config=ml_dataset.config.model_dump()
    config['extra_features']=['age_years']; config['scales']['age_years']={'minimum':5,'maximum':25,'decimals':0,'unit':'fixture'}
    with pytest.raises(ValidationError,match='JUSTIFICATION'): FeatureConfig.model_validate(config)
    config['extra_justification']='Explicit test-only configuration'
    assert 'age_years' in FeatureConfig.model_validate(config).features


def test_abstention_and_class_mapping(ml_dataset,bundles):
    row=ml_dataset.observations[2].model_copy(deep=True)
    assert predict_snapshot(row,None).status=='MODEL_NOT_AVAILABLE'
    row.eligible=False
    assert predict_snapshot(row,bundles['SVM']).status=='INELIGIBLE'
    row.eligible=True; row.values['average_grade']=None
    assert predict_snapshot(row,bundles['SVM']).status=='INSUFFICIENT_DATA'
    row.values['average_grade']=1000
    assert predict_snapshot(row,bundles['SVM']).status=='INCOMPATIBLE'
    assert class_mapping([2,0,1])=={2:'HIGH',0:'LOW',1:'MEDIUM'}
    with pytest.raises(MLDiagnostic): class_mapping([0,1])
    with pytest.raises(MLDiagnostic): class_mapping([1,2,3])


def test_metrics_not_estimable():
    result=metrics([0,0],[0,0])
    assert result['per_class']['HIGH']['recall'] is None
    assert result['per_class']['MEDIUM']['precision'] is None
    assert result['balanced_accuracy'] is None and result['auc'] is None


@pytest.mark.parametrize('attack',['traversal','symlink','hash','signature','versions','classes','schema','algorithm'])
def test_artifact_rejection_before_deserialization(ml_dataset,bundles,tmp_path,monkeypatch,attack):
    store=ArtifactStore(tmp_path/'private')
    key=store.save(bundles['DUMMY'],ml_dataset)
    directory=store.root/key
    def forbidden(*args,**kwargs): pytest.fail('Deserialization must not run')
    monkeypatch.setattr('app.ml.artifacts.joblib.load',forbidden)
    if attack=='traversal': key='../'+key
    elif attack=='symlink':
        path=directory/'pipeline.joblib'; outside=tmp_path/'outside'
        path.rename(outside); path.symlink_to(outside)
    elif attack=='hash': (directory/'pipeline.joblib').write_bytes(b'corrupted')
    else:
        envelope=json.loads((directory/'manifest.json').read_text())
        manifest=envelope['manifest']
        if attack=='signature': manifest['seed']=999
        if attack=='versions': manifest['versions']['scikit-learn']='0.0.0'
        if attack=='classes': manifest['class_order']=['HIGH','LOW','MEDIUM']
        if attack=='schema': manifest['feature_schema']['schema_version']='unknown'
        if attack=='algorithm': manifest['algorithm']='UNKNOWN'
        if attack!='signature':
            # Simula un artefacto interno antiguo/incompatible firmado; no crea bypass operativo.
            envelope['signature']=hmac.new(store._key(),canonical(manifest),hashlib.sha256).hexdigest()
        (directory/'manifest.json').write_bytes(canonical(envelope))
    with pytest.raises(MLDiagnostic): store.load(key)


def test_institutional_training_always_blocked(ml_dataset):
    from app.core.errors import AppError
    data=ml_dataset.model_copy(update={'scope':'INSTITUTIONAL'})
    with pytest.raises(AppError) as exc: compare(data)
    assert exc.value.code=='INSTITUTIONAL_PROCESSING_NOT_READY'
