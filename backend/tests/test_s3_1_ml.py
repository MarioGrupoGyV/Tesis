"""S3.1: contratos del generador, reserva externa y artefactos de simulación.

Estos resultados prueban software y supuestos del generador; no eficacia escolar.
Los artefactos de prueba viven únicamente en tmp_path, nunca en el volumen activo.
"""
from datetime import timedelta
import csv
import hashlib
import hmac
import io
import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from app.ml.artifacts import ArtifactStore, canonical
from app.ml.features import BASE_FEATURES, CLASSES, Dataset, LIMA, MLDiagnostic
from app.ml.predict import predict_snapshot
from app.ml.synthetic import HEADERS, SyntheticStudyConfig, generate, load_config
from app.ml.train import ALGORITHMS, compare_study


@pytest.fixture(scope='module')
def generated_study():
    return generate(load_config(), 1729)


@pytest.fixture(scope='module')
def study_comparison(generated_study):
    return compare_study(generated_study.dataset, load_config())


def test_generator_deterministic_uuid_dates_bytes_and_private_outcomes(generated_study):
    repeated = generate(load_config(), 1729)
    assert generated_study == repeated
    assert generated_study.csv_bytes == repeated.csv_bytes
    assert generated_study.dataset.model_dump_json() == repeated.dataset.model_dump_json()
    assert generated_study.manifest_json == repeated.manifest_json
    assert generated_study.study_id != generate(load_config(), 1730).study_id
    manifest = generated_study.manifest_json
    assert manifest['student_count'] == 60 and manifest['observation_count'] == 360
    assert manifest['data_origin'] == 'SYNTHETIC'
    assert manifest['csv_sha256'] == hashlib.sha256(generated_study.csv_bytes).hexdigest()
    csv_data = list(csv.DictReader(io.StringIO(generated_study.csv_bytes.decode())))
    assert tuple(csv_data[0]) == HEADERS and len(csv_data) == 360
    assert all(row['student_code'].startswith('SYN-') and len(row['student_code']) <= 40 for row in csv_data)
    assert not {'risk', 'future_outcome', 'student_name'} & set(csv_data[0])
    assert all(row.created_at.year == 2025 for row in generated_study.dataset.observations)
    for row, label in zip(generated_study.dataset.observations, generated_study.dataset.labels):
        assert label.observed_at > row.cutoff_at and label.available_at > label.observed_at
        assert label.risk == load_config().criterion.classify(label.future_outcome)
        assert (row.target_date - row.cutoff_at.astimezone(LIMA).date()).days == 14
        assert label.provenance != row.input_provenance


def test_v2_dataset_hash_survives_private_sorted_json_round_trip(generated_study):
    original = generated_study.dataset
    # Mirrors StudyStorage's canonical JSON writer, including all nested mappings.
    payload = json.loads(canonical(original.model_dump(mode='json')))
    loaded = Dataset.model_validate(payload)
    assert original == loaded
    assert original.model_dump_json() == loaded.model_dump_json()
    assert hashlib.sha256(loaded.model_dump_json().encode()).hexdigest() == generated_study.manifest_json['dataset_sha256']


def test_private_artifact_volume_supported_in_deployed_image_layout(tmp_path, monkeypatch):
    import app.ml.artifacts as artifacts
    monkeypatch.setattr(artifacts, '__file__', '/app/app/ml/artifacts.py')
    private = tmp_path / 'private-volume'
    assert ArtifactStore(private).root == private
    assert private.is_dir()
    with pytest.raises(MLDiagnostic, match='PRIVATE_STORAGE_REQUIRED'):
        ArtifactStore(Path('/app/unsafe'))


def test_private_artifacts_reject_entire_repository_not_only_backend(tmp_path, monkeypatch):
    import app.ml.artifacts as artifacts
    checkout = tmp_path / 'checkout'
    monkeypatch.setattr(artifacts, '__file__', str(checkout / 'backend' / 'app' / 'ml' / 'artifacts.py'))
    for destination in (checkout / 'backend' / 'unsafe', checkout / 'frontend' / 'unsafe', checkout / 'infra' / 'unsafe'):
        with pytest.raises(MLDiagnostic, match='PRIVATE_STORAGE_REQUIRED'):
            ArtifactStore(destination)
        assert not destination.exists()
    outside = tmp_path / 'private-volume'
    assert ArtifactStore(outside).root == outside


@pytest.mark.parametrize('change', [
    {'fit_date': '2025-03-01'}, {'external_cutoffs': ['2025-04-01']},
    {'timezone': 'UTC'}, {'student_count': 1001}, {'required_features': ['risk']},
    {'criterion': {'high_grade_below': 19, 'medium_grade_below': 14}},
])
def test_protocol_invalid_not_silently_repaired(change):
    data = load_config().model_dump(mode='json')
    data.update(change)
    with pytest.raises(ValidationError): SyntheticStudyConfig.model_validate(data)


@pytest.mark.parametrize('scope,origin,version', [
    ('ISOLATED_TEST', 'SYNTHETIC', 'ml-dataset-v1'),
    ('SYNTHETIC_STUDY', 'REAL', 'ml-dataset-v2'),
    ('SYNTHETIC_STUDY', 'SYNTHETIC', 'ml-dataset-v1'),
    ('INSTITUTIONAL', 'SYNTHETIC', 'ml-dataset-v1'),
])
def test_origin_scope_pairings_rejected(generated_study, scope, origin, version):
    data = generated_study.dataset.model_dump()
    data.update(scope=scope, schema_version=version)
    for row in data['observations']: row['data_origin'] = origin
    if scope != 'SYNTHETIC_STUDY': data['synthetic_protocol'] = None
    with pytest.raises(ValidationError): Dataset.model_validate(data)


def test_cv_and_external_are_distinct_no_groups_overlap_or_fit_leakage(generated_study, study_comparison):
    comparison = study_comparison
    assert set(comparison.bundles) == set(ALGORITHMS)
    report = comparison.report
    assert report['student_count'] == 60 and report['development_student_count'] == 48
    assert report['external_student_count'] == 12
    assert 2 <= report['folds_effective'] <= 5
    common = comparison.bundles['DUMMY'].manifest['partitions']
    for bundle in comparison.bundles.values():
        assert bundle.manifest['partitions'] == common
        plan = bundle.manifest['synthetic_evaluation']
        assert not set(plan['development_students']) & set(plan['external_students'])
        assert not set(plan['development_source_indices']) & set(plan['external_source_indices'])
        assert plan['development_labels_available_max'] < plan['fit_at'] < plan['external_cutoff_min']
        assert bundle.manifest['approved'] is False
        assert bundle.manifest['external_metrics']['class_order'] == list(CLASSES)
        assert not bundle.manifest['probabilities_calibrated']
        assert list(bundle.pipeline.feature_names_in_) == list(BASE_FEATURES)
        for split in bundle.manifest['partitions']:
            assert not set(split['train_students']) & set(split['validation_students'])
        assert set(row.student_key for row in comparison.training_dataset.observations) <= set(plan['development_students'])
    assert not {'development_students', 'external_students', 'partitions', 'external_predictions'} & set(report)
    assert sum(report['exclusions'].values()) + report['development_observation_count'] + report['external_observation_count'] == 360


def test_imputation_train_development_only_and_no_refit_on_external(study_comparison, generated_study):
    train = study_comparison.training_dataset.observations
    pipeline = study_comparison.bundles['SVM'].pipeline
    numeric = pipeline.named_steps['features'].named_transformers_['numeric']
    expected = np.nanmedian([np.nan if row.values['average_grade'] is None else row.values['average_grade'] for row in train])
    assert numeric.named_steps['imputer'].statistics_[0] == expected
    statistics = numeric.named_steps['imputer'].statistics_.copy()
    means = numeric.named_steps['scale'].mean_.copy()
    from app.ml.features import frame
    external = [row for row in generated_study.dataset.observations
                if row.student_key in generated_study.dataset.synthetic_protocol['external_students']]
    pipeline.predict(frame(external, generated_study.dataset.config))
    assert np.array_equal(statistics, numeric.named_steps['imputer'].statistics_)
    assert np.array_equal(means, numeric.named_steps['scale'].mean_)


def test_reserved_outcomes_do_not_choose_algorithm_or_fit(generated_study, study_comparison):
    changed = generated_study.dataset.model_copy(deep=True)
    external = set(changed.synthetic_protocol['external_students'])
    by_id = {row.snapshot_id: row for row in changed.observations}
    for label in changed.labels:
        if by_id[label.snapshot_id].student_key in external:
            label.future_outcome = {'average_grade': 20., 'attendance_pct': 100., 'activities_pct': 100., 'behavior_incidents': 0.}
            label.risk = 'LOW'
    after = compare_study(changed, load_config())
    assert after.selected_algorithm == study_comparison.selected_algorithm
    for algorithm in ALGORITHMS:
        assert after.bundles[algorithm].manifest['metrics'] == study_comparison.bundles[algorithm].manifest['metrics']
        assert after.bundles[algorithm].manifest['partitions'] == study_comparison.bundles[algorithm].manifest['partitions']
    assert after.bundles['DUMMY'].manifest['external_metrics']['per_class']['HIGH']['recall'] is None
    assert after.bundles['DUMMY'].manifest['external_metrics']['balanced_accuracy'] is None


@pytest.mark.parametrize('kind', ['group_overlap', 'missing_outcome', 'wrong_label', 'post_cutoff_feature', 'label_after_fit'])
def test_synthetic_temporal_provenance_rejections(generated_study, kind):
    data = generated_study.dataset.model_copy(deep=True)
    if kind == 'group_overlap': data.synthetic_protocol['external_students'].append(data.synthetic_protocol['development_students'][0])
    if kind == 'missing_outcome': data.labels[0].future_outcome = None
    if kind == 'wrong_label': data.labels[0].risk = 'LOW' if data.labels[0].risk != 'LOW' else 'HIGH'
    if kind == 'post_cutoff_feature':
        data.observations[0].feature_available_at['average_grade'] = data.observations[0].cutoff_at + timedelta(seconds=1)
    if kind == 'label_after_fit':
        # Nonestimable fit partition must diagnose, not fall back to row splitting.
        dev = set(data.synthetic_protocol['development_students'])
        by_id = {row.snapshot_id: row for row in data.observations}
        for label in data.labels:
            if by_id[label.snapshot_id].student_key in dev:
                label.available_at = data.evaluation_as_of
    with pytest.raises(MLDiagnostic): compare_study(data, load_config())


@pytest.mark.parametrize('algorithm', ALGORITHMS)
def test_synthetic_signed_artifact_round_trip_and_abstention(algorithm, generated_study, study_comparison, tmp_path):
    store = ArtifactStore(tmp_path / algorithm)
    bundle = study_comparison.bundles[algorithm]
    key = store.save(bundle, study_comparison.training_dataset)
    restored = store.load(key)
    row = next(row for row in generated_study.dataset.observations if all(value is not None for value in row.values.values()))
    result = predict_snapshot(row, restored)
    assert result.status == 'EVALUATED' and result.risk_level in CLASSES
    assert result == predict_snapshot(row, bundle)
    assert result.probability_low is None and not result.probabilities_calibrated
    missing = next(row for row in generated_study.dataset.observations if all(value is None for value in row.values.values()))
    # Research eligibility and operational policy are separate; even an eligible
    # caller cannot convert these missing observations into a LOW result.
    assert predict_snapshot(missing.model_copy(update={'eligible': True}), restored).status == 'INSUFFICIENT_DATA'
    assert (store.root / key / 'estimator.ubj').exists() == (algorithm == 'XGBOOST')


@pytest.mark.parametrize('attack', ['origin', 'scope', 'generator', 'holdout_overlap', 'version', 'corruption'])
def test_v2_artifacts_rejected_before_deserialization(attack, study_comparison, tmp_path, monkeypatch):
    store = ArtifactStore(tmp_path / 'private')
    key = store.save(study_comparison.bundles['DUMMY'], study_comparison.training_dataset)
    manifest_path = store.root / key / 'manifest.json'
    envelope = json.loads(manifest_path.read_bytes())
    manifest = envelope['manifest']
    if attack == 'origin': manifest['data_origin'] = 'REAL'
    if attack == 'scope': manifest['scope'] = 'ISOLATED_TEST'
    if attack == 'generator': manifest['generator_version'] = 'unknown'
    if attack == 'holdout_overlap':
        manifest['synthetic_evaluation']['external_students'].append(manifest['synthetic_evaluation']['development_students'][0])
    if attack == 'version': manifest['manifest_version'] = 'ml-artifact-v1'
    if attack == 'corruption': (store.root / key / 'pipeline.joblib').write_bytes(b'corrupted')
    envelope['signature'] = hmac.new(store._key(), canonical(manifest), hashlib.sha256).hexdigest()
    manifest_path.write_bytes(canonical(envelope))
    monkeypatch.setattr('app.ml.artifacts.joblib.load', lambda *args, **kwargs: pytest.fail('Unexpected deserialization'))
    with pytest.raises(MLDiagnostic): store.load(key)
