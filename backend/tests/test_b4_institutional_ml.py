"""Bloque 3B-2 (D/E): variables configurables y comparación institucional. Datos ficticios generados aquí."""
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import random
from uuid import uuid4
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from app.ml.artifacts import ArtifactStore
from app.ml.features import FeatureConfig, Dataset, Label, MLDiagnostic, Observation, Scale
from app.ml.institutional import ALGORITHMS, DEFAULT_REPETITIONS, compare_institutional, derive_seeds
from app.ml.manifest import ArtifactManifest
from app.ml.predict import predict_snapshot
from app.ml.synthetic import load_config
from app.ml.train import factory

LIMA = ZoneInfo('America/Lima')
FOUR = ['average_grade', 'attendance_pct', 'activities_pct', 'behavior_incidents']
STUDY = uuid4()


def config():
    scales = {'average_grade': Scale(minimum=0, maximum=20, decimals=2, unit='nota 0-20'),
              'attendance_pct': Scale(minimum=0, maximum=100, decimals=2, unit='%'),
              'activities_pct': Scale(minimum=0, maximum=100, decimals=2, unit='%'),
              'behavior_incidents': Scale(minimum=0, maximum=100, decimals=0, unit='conteo')}
    return FeatureConfig(criterion_version='RIESGO_V1', criterion_definition='RIESGO_V1: cinco componentes de 0 a 2 puntos',
        horizon_days=17, scales=scales, participation_values=[1, 2, 3, 4, 5], base_features=FOUR,
        inference_max_missing_fraction=0.4, required_features=['average_grade'])


def dataset(students=60):
    rng = random.Random(20260101)
    cfg = config()
    rows, labels = [], []
    for bimester, (cutoff, close) in enumerate(((date(2026, 4, 21), date(2026, 5, 8)), (date(2026, 6, 30), date(2026, 7, 17)))):
        for index in range(students):
            latent = rng.random()
            grade = round(20 - 12 * latent + rng.uniform(-1.5, 1.5), 2)
            attendance = round(max(40, min(100, 100 - 45 * latent + rng.uniform(-6, 6))), 2)
            activities = round(max(10, min(100, 100 - 60 * latent + rng.uniform(-8, 8))), 2)
            incidents = int(round(max(0, 6 * latent + rng.uniform(-1, 1))))
            values = {'average_grade': min(20, max(0, grade)), 'attendance_pct': attendance, 'activities_pct': activities,
                      'behavior_incidents': float(incidents)}
            cutoff_at = datetime.combine(cutoff, time(23, 59), tzinfo=LIMA)
            snapshot = uuid4()
            rows.append(Observation(student_key=f'E{index:03d}', snapshot_id=snapshot, enrollment_id=uuid4(), period_id=uuid4(),
                data_origin='REAL', schema_version='academic-v1', revision=1, window_start=cutoff - timedelta(days=43),
                available_at=cutoff_at, cutoff_at=cutoff_at, target_date=close, created_at=cutoff_at, eligible=True, values=values,
                feature_available_at={name: cutoff_at for name in FOUR}, input_provenance='snapshot:' + str(snapshot)))
            # Etiqueta de cierre: la fija el riesgo de referencia (aquí, una función ruidosa del latente), nunca las características.
            risk = 'HIGH' if latent + rng.uniform(-0.08, 0.08) > 0.62 else 'MEDIUM' if latent + rng.uniform(-0.08, 0.08) > 0.3 else 'LOW'
            observed = datetime.combine(close, time(17, 0), tzinfo=LIMA)
            labels.append(Label(snapshot_id=snapshot, risk=risk, criterion_version='RIESGO_V1', outcome_definition=cfg.criterion_definition,
                provenance='risk_references:' + str(uuid4()), observed_at=observed, available_at=observed + timedelta(days=3)))
    evaluation = max(label.available_at for label in labels)
    return Dataset(schema_version='ml-dataset-v1', scope='INSTITUTIONAL', provenance='fixture-ficticio', evaluation_as_of=evaluation,
                   config=cfg, observations=rows, labels=labels)


@pytest.fixture(scope='module')
def built():
    return dataset()


@pytest.fixture(scope='module')
def comparison(built):
    return compare_institutional(built, seed=1729, study_id=STUDY, leave_one_student_out=True)


def test_default_synthetic_dump_is_unchanged_and_four_features_work(built):
    synthetic = load_config(None).features
    assert 'base_features' not in synthetic.model_dump(mode='json')
    assert synthetic.features[3] == 'participation_level'
    cfg = built.config
    assert cfg.features == tuple(FOUR) and cfg.model_dump(mode='json')['base_features'] == FOUR
    assert FeatureConfig.model_validate(cfg.model_dump(mode='json')) == cfg
    pipeline = factory('SVM', cfg, 1)
    assert [item[0] for item in pipeline.named_steps['features'].transformers] == ['numeric']  # sin columna categórica


def test_comparison_reports_all_algorithms_with_mean_sd_and_aggregated_matrix(comparison, built):
    report, n = comparison.report, len(built.observations)
    assert set(report['algorithms']) == set(ALGORITHMS) == {'DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST'}
    assert report['repetitions'] == DEFAULT_REPETITIONS == 20 and report['students'] == 60 and report['observations'] == n == 120
    assert report['approval_kind'] == 'LOCAL_EXPLORATORY' and report['selected_algorithm'] in ALGORITHMS
    for name, item in report['algorithms'].items():
        summary = item['repeated_cv']
        assert summary['repetitions'] == 20
        assert np.array(summary['aggregated_confusion_matrix']).sum() == 20 * n          # 20 repeticiones × 120 observaciones
        assert summary['macro']['f1']['mean'] is not None and summary['macro']['f1']['sd'] is not None
        assert 0 <= summary['macro']['f1']['minimum'] <= summary['macro']['f1']['mean'] <= summary['macro']['f1']['maximum'] <= 1
        assert summary['cohen_kappa']['mean'] is not None and -1 <= summary['cohen_kappa']['minimum'] <= summary['cohen_kappa']['maximum'] <= 1
        assert set(item['leave_one_student_out']['per_class']) == {'LOW', 'MEDIUM', 'HIGH'}   # sensibilidad opcional (flag)
    # La regla aplica a la media: ningún algoritmo supera al elegido en F1 macro medio.
    means = {name: item['repeated_cv']['macro']['f1']['mean'] for name, item in report['algorithms'].items()}
    assert means[report['selected_algorithm']] == max(means.values())
    assert any('n = 60 estudiantes' in note for note in report['warnings']) and any('validación externa' in note for note in report['warnings'])
    assert set(report['support_by_class']) == {'LOW', 'MEDIUM', 'HIGH'}
    assert sum(item['students'] for item in report['support_by_class'].values()) >= 60


def test_unit_is_the_student_and_labels_do_not_leak_into_features(comparison, built):
    manifest = comparison.bundles['SVM'].manifest
    ArtifactManifest.model_validate({**manifest, 'artifact_key': uuid4().hex, 'artifact_sha256': 'a' * 64, 'files': {}})  # estructura válida
    keys = [row.student_key for row in built.observations]
    for split in manifest['partitions']:
        assert not set(split['train_students']) & set(split['validation_students'])      # ningún estudiante en ambos lados
    assert len({k for k in keys}) == 60 and len(keys) == 120                               # B1 y B2 del mismo estudiante
    assert set(manifest['feature_schema']['scales']) == set(FOUR) and 'risk' not in str(manifest['feature_schema']).lower().replace('riesgo', '')
    assert manifest['scope'] == 'INSTITUTIONAL_STUDY' and manifest['data_origin'] == 'REAL'
    assert manifest['institutional_evaluation']['seeds'] == derive_seeds(1729, 20)


def test_same_seed_reproduces_report_and_different_seed_changes_it(comparison, built):
    again = compare_institutional(built, seed=1729, study_id=STUDY, leave_one_student_out=True)
    assert again.report['report_sha256'] == comparison.report['report_sha256']
    assert again.selected_algorithm == comparison.selected_algorithm
    other = compare_institutional(built, seed=7, study_id=STUDY)
    assert other.report['report_sha256'] != comparison.report['report_sha256']
    assert other.report['source_dataset_hash'] == comparison.report['source_dataset_hash']  # mismo dataset, otra semilla


def test_artifact_roundtrip_and_prediction_with_four_variables(comparison, built, tmp_path):
    store = ArtifactStore(tmp_path / 'ml')
    key = store.save(comparison.bundles[comparison.selected_algorithm], comparison.training_dataset)
    manifest, loaded_config, _ = store.inspect(key)
    assert manifest['scope'] == 'INSTITUTIONAL_STUDY' and loaded_config.features == tuple(FOUR)
    bundle = store.load(key)
    observation = built.observations[0]
    result = predict_snapshot(observation, bundle)
    assert result.status == 'EVALUATED' and result.risk_level in ('LOW', 'MEDIUM', 'HIGH')
    incomplete = observation.model_copy(update={'values': {**observation.values, 'average_grade': None}})
    assert predict_snapshot(incomplete, bundle).status == 'INSUFFICIENT_DATA'               # requerida ausente: sin riesgo inventado
    synthetic_like = observation.model_copy(update={'data_origin': 'SYNTHETIC'})
    assert predict_snapshot(synthetic_like, bundle).status == 'INCOMPATIBLE'                # un modelo REAL no evalúa cortes SYNTHETIC


def test_invalid_configuration_is_rejected(built):
    for kwargs in ({'repetitions': 5}, {'requested_folds': 9}, {'seed': -1}):
        with pytest.raises(MLDiagnostic):
            compare_institutional(built, **{'seed': 1, 'study_id': STUDY, **kwargs})
    other = built.model_copy(update={'scope': 'ISOLATED_TEST'})
    with pytest.raises(MLDiagnostic):
        compare_institutional(other, seed=1, study_id=STUDY)


def test_cohen_kappa_matches_the_textbook_values():
    from app.ml.institutional import cohen_kappa
    assert cohen_kappa([[10, 0, 0], [0, 10, 0], [0, 0, 10]]) == pytest.approx(1.0)
    assert cohen_kappa([[5, 5], [5, 5]]) == pytest.approx(0.0)
    assert cohen_kappa([[20, 5], [10, 15]]) == pytest.approx(0.4)          # po=0,7; pe=0,5 → (0,7-0,5)/(1-0,5)
    assert cohen_kappa([[0, 0], [0, 0]]) is None


def test_comparison_does_not_depend_on_row_order_or_internal_identifiers(built, comparison):
    """Repetir la corrida en otra instalación (otros UUID internos, otro orden de filas) da las mismas métricas con la misma semilla."""
    mapping = {row.snapshot_id: uuid4() for row in built.observations}
    shuffled_rows = [row.model_copy(update={'snapshot_id': mapping[row.snapshot_id], 'enrollment_id': uuid4()}) for row in built.observations]
    random.Random(7).shuffle(shuffled_rows)
    labels = [label.model_copy(update={'snapshot_id': mapping[label.snapshot_id]}) for label in built.labels]
    random.Random(8).shuffle(labels)
    other = built.model_copy(update={'observations': shuffled_rows, 'labels': labels})
    again = compare_institutional(other, seed=1729, study_id=STUDY, leave_one_student_out=True)
    assert again.selected_algorithm == comparison.selected_algorithm
    for name in ALGORITHMS:
        assert again.report['algorithms'][name] == comparison.report['algorithms'][name]
