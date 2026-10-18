"""Bloque 5.1: detección fuera de muestra (validada) por modelo y bimestre. Datos ficticios; sin códigos ni nombres reales."""
from datetime import date

import numpy as np
import pytest

from app.ml.features import MLDiagnostic
from app.ml.institutional import (ALGORITHMS, DETECTION_DEFINITION, bimester_codes, compare_institutional, detection_counts,
                                  detection_rates, detection_report)
from test_b4_institutional_ml import STUDY, dataset

CLOSE_B1, CLOSE_B2 = date(2026, 5, 8), date(2026, 7, 17)


@pytest.fixture(scope='module')
def built():
    return dataset()


@pytest.fixture(scope='module')
def comparison(built):
    return compare_institutional(built, seed=1729, study_id=STUDY, bimesters={CLOSE_B1: 'B1', CLOSE_B2: 'B2'})


def test_counts_and_rates_match_a_direct_calculation_on_a_known_case():
    reference = np.array([0, 0, 1, 1, 1, 2, 2, 2, 2])
    predicted = np.array([0, 1, 0, 1, 2, 0, 1, 2, 2])
    counts = detection_counts(reference, predicted, np.ones(len(reference), dtype=bool))
    assert counts == {'reference_low': 2, 'reference_medium': 3, 'reference_high': 4, 'low_flagged': 1, 'medium_flagged': 2,
                      'high_flagged': 3, 'high_as_low': 1}
    rates = detection_rates(counts)
    assert rates['detection'] == pytest.approx(5 / 7) and rates['medium_detected'] == pytest.approx(2 / 3)
    assert rates['high_detected'] == pytest.approx(3 / 4) and rates['high_as_low'] == pytest.approx(1 / 4)
    assert rates['low_flagged'] == pytest.approx(1 / 2)
    only_low = detection_counts(reference, predicted, reference == 0)
    assert detection_rates(only_low)['detection'] is None and detection_rates(only_low)['high_detected'] is None   # sin denominador: no estimable


def test_known_matrix_gives_the_expected_rate_and_a_wrong_matrix_is_refused():
    repetition = {'reference_low': 40, 'reference_medium': 32, 'reference_high': 48, 'low_flagged': 5, 'medium_flagged': 28,
                  'high_flagged': 48, 'high_as_low': 0}
    # 20 repeticiones iguales: Bajo 800 (100 marcados), Medio 640 (560 marcados, 80 dejados en Bajo), Alto 960 (todos marcados).
    matrix = np.array([[700, 60, 40], [80, 400, 160], [0, 100, 860]])
    report = detection_report([{'TOTAL': dict(repetition)} for _ in range(20)], matrix)
    assert report['definition'] == DETECTION_DEFINITION and report['metric_basis'] == 'OUT_OF_FOLD'
    assert report['total']['detection']['mean'] == pytest.approx(0.95) and report['total']['detection']['sd'] == pytest.approx(0.0)
    assert report['total']['pooled']['detected'] == 1520 and report['total']['pooled']['reference_at_risk'] == 1600
    assert report['total']['high_as_low']['mean'] == 0.0 and report['total']['low_flagged']['mean'] == pytest.approx(5 / 40)
    with pytest.raises(MLDiagnostic, match='DETECTION_MATRIX_MISMATCH'):
        detection_report([{'TOTAL': dict(repetition)} for _ in range(20)], np.array([[700, 60, 40], [81, 399, 160], [0, 100, 860]]))


def test_report_has_every_model_and_the_totals_add_up(comparison):
    assert set(comparison.report['algorithms']) == set(ALGORITHMS)
    for name, item in comparison.report['algorithms'].items():
        detection, matrix = item['detection'], np.array(item['repeated_cv']['aggregated_confusion_matrix'])
        total = detection['total']
        assert total['repetitions'] == 20 and set(detection['by_bimester']) == {'B1', 'B2'}
        # La detección sale de la misma validación cruzada que la matriz agregada: los números tienen que coincidir.
        assert total['pooled']['detected'] == matrix[1][1] + matrix[1][2] + matrix[2][1] + matrix[2][2]
        assert total['pooled']['reference_at_risk'] == matrix[1].sum() + matrix[2].sum()
        assert total['pooled']['high_as_low'] == matrix[2][0] and total['pooled']['low_flagged'] == matrix[0][1] + matrix[0][2]
        assert total['detection']['mean'] == pytest.approx(total['pooled']['detected'] / total['pooled']['reference_at_risk'])
        for key in ('reference_low', 'reference_medium', 'reference_high', 'low_flagged', 'medium_flagged', 'high_flagged', 'high_as_low',
                    'reference_at_risk', 'detected'):
            assert detection['by_bimester']['B1']['pooled'][key] + detection['by_bimester']['B2']['pooled'][key] == total['pooled'][key], (name, key)
        assert total['pooled']['reference_at_risk'] == 20 * total['reference_at_risk_per_repetition']
        assert total['detection']['sd'] is not None and 0.0 <= total['detection']['mean'] <= 1.0


def test_the_majority_class_baseline_detects_everyone_so_false_alarms_must_be_reported(comparison):
    dummy = comparison.report['algorithms']['DUMMY']['detection']['total']
    forest = comparison.report['algorithms']['RANDOM_FOREST']['detection']['total']
    assert dummy['low_flagged']['mean'] > 0.0                       # marcar a todos como Alto detecta mucho y genera falsas alarmas
    assert forest['detection']['mean'] > 0.5 and forest['low_flagged']['mean'] < dummy['low_flagged']['mean'] + 1e-12


def test_only_validation_predictions_are_counted_and_students_never_cross_folds(built, comparison):
    rows = sorted(built.observations, key=lambda row: (row.student_key, row.cutoff_at))        # el mismo orden canónico de la comparación
    manifest = comparison.bundles['RANDOM_FOREST'].manifest
    seen = set()
    for fold in manifest['partitions']:
        training = {rows[index].student_key for index in fold['train']}
        validation = {rows[index].student_key for index in fold['validation']}
        assert not training & validation                                           # ningún estudiante a la vez en entrenamiento y validación
        assert {rows[index].student_key for index in fold['validation']} == set(fold['validation_students'])
        for student in validation:                                                  # sus dos bimestres viajan juntos
            assert {index for index, row in enumerate(rows) if row.student_key == student} <= set(fold['validation'])
        seen |= set(fold['validation'])
    assert seen == set(range(len(rows)))                                           # cada observación se valida exactamente una vez por repetición
    total = comparison.report['algorithms']['RANDOM_FOREST']['detection']['total']['pooled']
    labels = {label.snapshot_id: label.risk for label in built.labels}
    counts = {risk: sum(1 for row in rows if labels[row.snapshot_id] == risk) for risk in ('LOW', 'MEDIUM', 'HIGH')}
    assert (total['reference_low'], total['reference_medium'], total['reference_high']) == tuple(20 * counts[risk] for risk in ('LOW', 'MEDIUM', 'HIGH'))


def test_same_seed_reproduces_the_detection_and_a_different_seed_changes_it(built, comparison):
    again = compare_institutional(built, seed=1729, study_id=STUDY, bimesters={CLOSE_B1: 'B1', CLOSE_B2: 'B2'})
    other = compare_institutional(built, seed=1730, study_id=STUDY, bimesters={CLOSE_B1: 'B1', CLOSE_B2: 'B2'})
    for name in ALGORITHMS:
        assert again.report['algorithms'][name]['detection'] == comparison.report['algorithms'][name]['detection']
        assert again.report['algorithms'][name]['repeated_cv'] == comparison.report['algorithms'][name]['repeated_cv']
    assert other.report['algorithms']['RANDOM_FOREST']['detection'] != comparison.report['algorithms']['RANDOM_FOREST']['detection']


def test_detection_does_not_change_the_published_metrics(built, comparison):
    """Añadir la detección no toca el entrenamiento ni las particiones: `repeated_cv` y el manifiesto del artefacto quedan como estaban."""
    manifest = comparison.bundles['RANDOM_FOREST'].manifest
    assert 'detection' not in manifest['metrics'] and 'detection' not in manifest['metrics']['repeated_cv']
    assert 'detection' not in comparison.report['algorithms']['RANDOM_FOREST']['repeated_cv']


def test_bimesters_come_from_the_protocol_or_from_the_date_order(built):
    rows = built.observations
    assert set(bimester_codes(rows, {CLOSE_B1: 'P1', CLOSE_B2: 'P2'})) == {'P1', 'P2'}
    assert set(bimester_codes(rows, None)) == {'B1', 'B2'}
    with pytest.raises(MLDiagnostic, match='BIMESTER_NOT_MAPPED'):
        bimester_codes(rows, {CLOSE_B1: 'P1'})


def test_report_json_has_no_student_codes(comparison, built):
    text = str(comparison.report['algorithms'])
    assert not any(row.student_key in text for row in built.observations)
