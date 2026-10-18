"""Bloque 7: colector de `compare_institutional` y exportación para SPSS. Datos ficticios; sin códigos ni nombres reales.

Garantías: sin colector la comparación da EXACTAMENTE lo de antes (huella calculada con el código anterior al cambio); con colector da lo mismo
aunque el colector altere lo que recibe; lo recogido reproduce `summarize` y `detection_report`; las tablas y la verificación se calculan bien; el
exportador se niega a escribir dentro de Git y a trabajar con entradas cuyo SHA-256 no coincide.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import UUID, uuid5, NAMESPACE_URL

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
import convert_real_excel as converter  # noqa: E402
import export_spss as exporter  # noqa: E402
import run_real_study as runner  # noqa: E402
from app.ml.institutional import (ALGORITHMS, RepetitionRecord, cohen_kappa, compare_institutional, derive_seeds, detection_report,  # noqa: E402
                                  summarize)
from test_b4_institutional_ml import dataset  # noqa: E402
from test_b6_convert_excel import NAME_WORDS, fictitious_sheets, write_book  # noqa: E402

# Huella de la comparación determinista con el código ANTERIOR al colector (golden07.py, dos ejecuciones idénticas).
GOLDEN_REPORT_SHA256 = '58213afb99070da064fd6fa3f54c4bcf9ba941586d8556144469cf500668937d'
GOLDEN_MANIFESTS_SHA256 = '1460d415ca9c4b7a45404b11afd442d6801b16d8f9dc21dea8e9d3e1d6796463'
SEED_USED = 1729


def deterministic_dataset():
    """El dataset ficticio de las pruebas del Bloque 4 con identificadores fijos: la huella no depende de uuid4."""
    ids = {}

    def stable(value, kind):
        return ids.setdefault((kind, value), uuid5(NAMESPACE_URL, f'golden07:{kind}:{len(ids)}'))
    built = dataset()
    rows = [row.model_copy(update={'snapshot_id': stable(row.snapshot_id, 's'), 'enrollment_id': stable(row.enrollment_id, 'e'),
                                   'period_id': UUID(int=7), 'input_provenance': 'snapshot:fixed'}) for row in built.observations]
    mapping = {old.snapshot_id: new.snapshot_id for old, new in zip(built.observations, rows)}
    labels = [label.model_copy(update={'snapshot_id': mapping[label.snapshot_id], 'provenance': 'risk_references:fixed'}) for label in built.labels]
    return built.model_copy(update={'observations': rows, 'labels': labels})


def fingerprint(result):
    manifests = {name: {'metrics': bundle.manifest['metrics'], 'validation_predictions': bundle.manifest['validation_predictions'],
                        'fold_metrics': bundle.manifest['fold_metrics']} for name, bundle in result.bundles.items()}
    return result.report['report_sha256'], hashlib.sha256(json.dumps(manifests, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def compare(built, collector=None):
    bimesters = {built.observations[0].target_date: 'B1', built.observations[-1].target_date: 'B2'}
    return compare_institutional(built, seed=SEED_USED, study_id=UUID(int=11), bimesters=bimesters, collector=collector)


class Hostile:
    """Guarda copias intactas de cada registro y después los destroza: la comparación no puede enterarse."""

    def __init__(self):
        self.kept = []

    def __call__(self, record):
        self.kept.append(RepetitionRecord(**{**record.__dict__, 'metrics': deepcopy(record.metrics), 'detection': deepcopy(record.detection),
                                             'predictions': record.predictions.copy(), 'reference': record.reference.copy()}))
        record.predictions[:] = 0
        record.reference[:] = 9
        record.metrics['accuracy'] = -1.0
        record.metrics['confusion_matrix'][0][0] = 10 ** 6
        record.detection['TOTAL']['low_flagged'] = 10 ** 6


@pytest.fixture(scope='module')
def built():
    return deterministic_dataset()


@pytest.fixture(scope='module')
def plain(built):
    return compare(built)


@pytest.fixture(scope='module')
def hostile(built):
    collector = Hostile()
    return compare(built, collector), collector.kept


# ---------------------------------------------------------------- 1. el colector no cambia nada
def test_without_collector_the_comparison_is_identical_to_the_one_before_the_change(plain):
    assert fingerprint(plain) == (GOLDEN_REPORT_SHA256, GOLDEN_MANIFESTS_SHA256)
    assert 'collector' not in json.dumps(plain.report)


def test_with_collector_the_results_are_identical_even_if_the_collector_tampers_with_what_it_receives(plain, hostile):
    result, kept = hostile
    assert len(kept) == 20 * len(ALGORITHMS)
    assert result.report == plain.report and result.selected_algorithm == plain.selected_algorithm
    assert fingerprint(result) == (GOLDEN_REPORT_SHA256, GOLDEN_MANIFESTS_SHA256)


def test_records_reproduce_summarize_and_the_detection_report(plain, hostile):
    _, kept = hostile
    rows = plain.training_dataset.observations
    labels = {label.snapshot_id: label.risk for label in plain.training_dataset.labels}
    seeds = derive_seeds(SEED_USED, 20)
    assert [(record.repetition, record.algorithm) for record in kept] == [(rep, name) for rep in range(20) for name in ALGORITHMS]
    for name in ALGORITHMS:
        mine = [record for record in kept if record.algorithm == name]
        pooled = np.sum([np.array(record.metrics['confusion_matrix']) for record in mine], axis=0)
        assert summarize([record.metrics for record in mine], pooled) == plain.report['algorithms'][name]['repeated_cv']
        assert detection_report([record.detection for record in mine], pooled) == plain.report['algorithms'][name]['detection']
        for record in mine:
            assert record.seed == seeds[record.repetition] and record.kappa == cohen_kappa(record.metrics['confusion_matrix'])
    first = kept[0]
    assert list(first.keys) == [(row.student_key, row.cutoff_at) for row in rows]                 # mismo orden canónico que training_dataset
    assert [('LOW', 'MEDIUM', 'HIGH')[value] for value in first.reference] == [labels[row.snapshot_id] for row in rows]
    assert set(first.bimesters) == {'B1', 'B2'} and all(set(np.unique(record.predictions)) <= {0, 1, 2} for record in kept)
    assert all(record.keys is first.keys and np.array_equal(record.reference, first.reference) for record in kept)


# ---------------------------------------------------------------- 2. tablas
def test_modal_class_ties_go_to_the_higher_risk_class_and_are_counted():
    matrix = np.array([[0, 1, 2, 2, 0, 0], [0, 1, 1, 2, 2, 1], [0, 2, 1, 0, 0, 2]])
    modal, best, tied = exporter.modal_class(matrix)
    assert modal.tolist() == [0, 1, 1, 2, 0, 2] and best.tolist() == [3, 2, 2, 2, 2, 1]
    assert tied.tolist() == [False, False, False, False, False, True]               # la última columna: 0, 1, 2 una vez cada una → gana Alto
    even = np.array([[0, 2, 1], [0, 2, 1], [2, 0, 1], [2, 0, 1]])
    modal, best, tied = exporter.modal_class(even)
    assert modal.tolist() == [2, 2, 1] and best.tolist() == [2, 2, 4] and tied.tolist() == [True, True, False]


def handmade_records():
    """Cuatro filas (E-A bimestre 1 y 2, E-B bimestre 1 y 2), tres repeticiones, cuatro algoritmos."""
    keys = (('S1', 1), ('S1', 2), ('S2', 1), ('S2', 2))
    codes, reference = ('B1', 'B2', 'B1', 'B2'), np.array([0, 0, 1, 2])
    predictions = {'RANDOM_FOREST': [[0, 1, 0, 2], [0, 1, 1, 2], [0, 0, 2, 2]],        # modal: 0, 1, (0,1,2→2 empate), 2
                   'SVM': [[0, 0, 1, 2]] * 3, 'XGBOOST': [[1, 1, 1, 1]] * 3, 'DUMMY': [[2, 2, 2, 2]] * 3}
    return [SimpleNamespace(algorithm=name, repetition=index, predictions=np.array(row), reference=reference, keys=keys, bimesters=codes)
            for name, rows in predictions.items() for index, row in enumerate(rows)]


def test_prediction_rows_use_the_modal_class_and_leave_missing_what_does_not_apply():
    rows, ties, repetitions = exporter.predictions_table(handmade_records(), {'S1': 'A', 'S2': 'B'}, {'B1': 1, 'B2': 2})
    assert repetitions == 3 and ties == {'RANDOM_FOREST': 1, 'SVM': 0, 'XGBOOST': 0, 'DUMMY': 0}
    assert [list(row) for row in rows] == [exporter.PREDICTION_COLUMNS] * 4
    assert [(row['codigo'], row['seccion'], row['bimestre'], row['riesgo_ref']) for row in rows] == [('S1', 1, 1, 1), ('S1', 1, 2, 1), ('S2', 2, 1, 2), ('S2', 2, 2, 3)]
    assert [row['riesgo_pred_rf'] for row in rows] == [1, 2, 3, 3]                       # el empate de la fila 3 (Bajo, Medio, Alto) lo gana Alto
    assert [row['riesgo_pred_svm'] for row in rows] == [1, 1, 2, 3] and [row['riesgo_pred_dummy'] for row in rows] == [3, 3, 3, 3]
    assert [row['riesgo_pred_rf_rep1'] for row in rows] == [1, 2, 1, 3]                  # RF en la repetición 1
    assert [row['acuerdo_rf'] for row in rows] == [1.0, pytest.approx(2 / 3), pytest.approx(1 / 3), 1.0]
    # Referencia Bajo → solo falsa alarma; Medio o Alto → solo detección.
    assert [row['detectado_rf'] for row in rows] == [None, None, 1, 1]
    assert [row['falsa_alarma_rf'] for row in rows] == [0, 1, None, None]


def test_prediction_rows_refuse_records_that_do_not_line_up():
    records = handmade_records()
    records[3].reference = np.array([0, 0, 1, 1])
    with pytest.raises(exporter.StopRun, match='RECORDS_INCONSISTENT'):
        exporter.predictions_table(records, {'S1': 'A', 'S2': 'B'}, {'B1': 1, 'B2': 2})
    with pytest.raises(exporter.StopRun, match='RECORDS_INCOMPLETE'):
        exporter.predictions_table([record for record in handmade_records() if record.algorithm != 'SVM'], {'S1': 'A', 'S2': 'B'}, {'B1': 1, 'B2': 2})


def test_metrics_table_has_one_row_per_repetition_and_the_columns_of_the_prompt(hostile, plain):
    _, kept = hostile
    rows = exporter.metrics_table(kept)
    columns = exporter.metric_columns()
    assert len(rows) == 20 and [list(row) for row in rows] == [columns] * 20 and [row['repeticion'] for row in rows] == list(range(1, 21))
    assert columns[:5] == ['repeticion', 'acc_rf', 'acc_svm', 'acc_xgb', 'acc_dummy'] and len(columns) == 1 + 7 * 4
    assert {name.rsplit('_', 1)[0] for name in columns[1:]} == {'acc', 'balacc', 'f1', 'kappa', 'recallhigh', 'det', 'fa'}
    # Cada celda es lo que ya calculó la repetición; las medias y desviaciones reproducen el informe de la comparación.
    for model, suffix in exporter.SUFFIX.items():
        one = next(record for record in kept if record.algorithm == model and record.repetition == 3)
        assert rows[3][f'acc_{suffix}'] == one.metrics['accuracy'] and rows[3][f'kappa_{suffix}'] == one.kappa
        assert rows[3][f'recallhigh_{suffix}'] == one.metrics['per_class']['HIGH']['recall']
        for metric, _ in exporter.METRIC_LABELS:
            published = exporter.in_process_spread(plain.report['algorithms'][model], metric)
            mine = exporter.spread_of([row[f'{metric}_{suffix}'] for row in rows])
            assert abs(mine['mean'] - published['mean']) <= 1e-12 and abs(mine['sd'] - published['sd']) <= 1e-12


def test_spss_variable_specs_cover_every_column_with_labels_value_labels_and_measurement_levels():
    specs = exporter.table_specs({'S1': 'A', 'S2': 'B'}, ['B1', 'B2'], 20)
    assert [item['nombre'] for item in specs[exporter.METRICS_FILE]['variables']] == exporter.metric_columns()
    assert [item['nombre'] for item in specs[exporter.PREDICTIONS_FILE]['variables']] == exporter.PREDICTION_COLUMNS
    every = [item for table in specs.values() for item in table['variables']]
    assert all(item['etiqueta'] and len(item['nombre']) <= 64 and len(item['etiqueta']) <= 256 for item in every)
    by_name = {item['nombre']: item for item in specs[exporter.PREDICTIONS_FILE]['variables']}
    assert by_name['riesgo_ref']['valores'] == {'1': 'Bajo', '2': 'Medio', '3': 'Alto'} and by_name['riesgo_ref']['medida'] == 'ordinal'
    assert all(by_name[name]['medida'] == 'ordinal' for name in exporter.PREDICTION_COLUMNS if name.startswith('riesgo_'))
    assert by_name['seccion']['valores'] == {'1': 'A', '2': 'B'} and by_name['bimestre']['valores'] == {'1': 'Primer bimestre', '2': 'Segundo bimestre'}
    assert [by_name[name]['medida'] for name in ('codigo', 'seccion', 'bimestre')] == ['nominal'] * 3 and by_name['codigo']['tipo'] == 'string'
    assert all(item['medida'] == 'scale' for item in specs[exporter.METRICS_FILE]['variables'])


def test_csv_files_are_utf8_with_bom_use_empty_cells_for_missing_and_round_trip_floats_exactly(tmp_path):
    value = 0.1 + 0.2
    path = tmp_path / 'tabla.csv'
    exporter.write_csv(path, ['a', 'b', 'c'], [{'a': 1, 'b': value, 'c': None}, {'a': np.int64(2), 'b': np.float64(1 / 3), 'c': float('nan')}])
    raw = path.read_bytes()
    assert raw.startswith(b'\xef\xbb\xbf') and b'\r\n' in raw
    rows = exporter.read_csv(path)
    assert rows[0] == {'a': '1', 'b': repr(value), 'c': ''} and float(rows[0]['b']) == value and float(rows[1]['b']) == 1 / 3 and rows[1]['c'] == ''


# ---------------------------------------------------------------- 3. verificación contra el resumen publicado
def reference_from(report, built):
    models = runner.model_table(report)
    close = sorted({row.target_date for row in built.observations})
    labels = {label.snapshot_id: label.risk for label in built.labels}
    distribution = {code: [sum(1 for row in built.observations if row.target_date == day and labels[row.snapshot_id] == level)
                           for level in ('LOW', 'MEDIUM', 'HIGH')] for code, day in zip(('B1', 'B2'), close)}
    return {'comparison': {'models': models, 'repetitions': 20, 'observations': len(built.observations), 'students': len({r.student_key for r in built.observations})},
            'reference_distribution_low_medium_high': distribution}


@pytest.fixture(scope='module')
def exported(tmp_path_factory, plain, hostile, built):
    _, kept = hostile
    folder = tmp_path_factory.mktemp('export')
    sections = {row.student_key: ('A' if int(row.student_key[1:]) < 30 else 'B') for row in plain.training_dataset.observations}
    exporter.write_csv(folder / f'{exporter.METRICS_FILE}.csv', exporter.metric_columns(), exporter.metrics_table(kept))
    rows, ties, _ = exporter.predictions_table(kept, sections, {'B1': 1, 'B2': 2})
    exporter.write_csv(folder / f'{exporter.PREDICTIONS_FILE}.csv', exporter.PREDICTION_COLUMNS, rows)
    return folder, ties, rows


def test_verification_reproduces_a_reference_built_from_the_same_run(exported, plain, built):
    folder, ties, rows = exported
    assert len(rows) == 120 and len({row['codigo'] for row in rows}) == 60
    result = exporter.verify_exports(folder, reference_from(plain.report, built), plain.report, ['B1', 'B2'], ties)
    assert result['reproduce_resumen_publicado'] is True and result['diferencias'] == [] and all(result['comprobaciones'].values())
    assert result['maxima_diferencia_absoluta'] <= 1e-12 and result['filas'] == {'metricas': 20, 'predicciones': 120, 'estudiantes': 60}
    assert result['distribucion_referencia_bajo_medio_alto']['exportada'] == result['distribucion_referencia_bajo_medio_alto']['publicada']
    assert set(result['rf_clase_modal']) == {'TOTAL', 'B1', 'B2'} and result['empates_clase_modal_por_modelo'] == ties
    total = result['rf_clase_modal']['TOTAL']
    assert total['filas'] == 120 and total['en_riesgo'] + total['referencia_bajo'] == 120
    assert total['deteccion'] == pytest.approx(total['detectados'] / total['en_riesgo']) and -1 <= total['kappa_referencia_vs_modal'] <= 1
    assert [result['rf_clase_modal'][code]['filas'] for code in ('B1', 'B2')] == [60, 60]


def test_verification_reports_the_difference_and_does_not_reproduce_when_a_published_number_differs(exported, plain, built):
    folder, ties, _ = exported
    for tamper in ('mean', 'sd'):
        reference = reference_from(plain.report, built)
        reference['comparison']['models']['SVM']['accuracy'][tamper] += 1e-9
        result = exporter.verify_exports(folder, reference, plain.report, ['B1', 'B2'], ties)
        assert result['reproduce_resumen_publicado'] is False and result['comprobaciones']['metricas_dentro_de_tolerancia'] is False
        assert [(item['modelo'], item['metrica'], item['estadistico']) for item in result['diferencias']] == [('SVM', 'acc', 'media' if tamper == 'mean' else 'sd')]
    reference = reference_from(plain.report, built)
    reference['reference_distribution_low_medium_high']['B1'][0] += 1
    assert exporter.verify_exports(folder, reference, plain.report, ['B1', 'B2'], ties)['reproduce_resumen_publicado'] is False


# ---------------------------------------------------------------- 4. Dataset desde los archivos del conversor, sin base de datos
@pytest.fixture(scope='module')
def converted(tmp_path_factory):
    base = tmp_path_factory.mktemp('conversor')
    sheets, _ = fictitious_sheets()
    out = base / 'entrada'
    converter.convert(write_book(base / 'ficticio.xlsx', sheets), out)
    return out


def test_dataset_from_files_has_the_same_shape_features_and_labels_as_the_database_path(converted):
    inputs = runner.Inputs(converted)
    result, exclusions = exporter.build_dataset(inputs)
    assert exclusions == {} and len(result.observations) == len(inputs.cut_rows) == len(result.labels)
    assert result.scope == 'INSTITUTIONAL' and list(result.config.features) == ['average_grade', 'attendance_pct', 'activities_pct', 'behavior_incidents']
    assert {row.student_key for row in result.observations} == set(inputs.codes) and all(row.data_origin == 'REAL' for row in result.observations)
    labels = {label.snapshot_id: label.risk for label in result.labels}
    for code, item in inputs.calendar.items():
        counts = [sum(1 for row in result.observations if row.target_date == item['close'] and labels[row.snapshot_id] == level) for level in runner.LEVELS]
        assert counts == [inputs.expected_levels[code][level] for level in runner.LEVELS]       # RIESGO_V1 recalculado = el del resumen del conversor
    again, _ = exporter.build_dataset(runner.Inputs(converted))
    assert again.model_dump_json() == result.model_dump_json()                                   # determinista


def test_worker_end_to_end_writes_the_files_and_keeps_students_and_names_out_of_the_verification(converted, tmp_path):
    inputs = runner.Inputs(converted)
    zero = {'mean': 0.0, 'sd': 0.0}
    scope = {'detection': zero, 'low_flagged': zero}
    models = {name: {'accuracy': zero, 'balanced_accuracy': zero, 'macro_f1': zero, 'cohen_kappa': zero, 'recall_high': zero,
                     'detection': {'total': scope, 'B1': scope, 'B2': scope}} for name in ALGORITHMS}
    reference = tmp_path / 'referencia.json'
    reference.write_text(json.dumps({'comparison': {'models': models, 'repetitions': 20, 'observations': len(inputs.cut_rows), 'students': len(inputs.codes)},
                                     'reference_distribution_low_medium_high': {}}), encoding='utf-8')
    results = tmp_path / 'salida'
    results.mkdir()
    args = SimpleNamespace(input=converted, results=results, reference=reference)
    assert exporter.worker(args) == 0
    assert sorted(item.name for item in results.iterdir()) == ['Metricas_por_repeticion.csv', 'Predicciones_fuera_de_muestra.csv', 'variables.json', 'verificacion.json']
    assert len(exporter.read_csv(results / 'Metricas_por_repeticion.csv')) == 20
    predictions = exporter.read_csv(results / 'Predicciones_fuera_de_muestra.csv')
    assert len(predictions) == len(inputs.cut_rows) and {row['codigo'] for row in predictions} == set(inputs.codes)
    text = (results / 'verificacion.json').read_text(encoding='utf-8')
    verification = json.loads(text)
    assert not any(code in text for code in inputs.codes) and not any(word in text for word in NAME_WORDS)
    assert verification['reproduce_resumen_publicado'] is False and verification['comprobaciones']['coincide_con_informe_en_proceso'] is True
    assert verification['parametros'] == {'semilla': 0, 'repeticiones': 20, 'pliegues': 5, 'modelos': ['RANDOM_FOREST', 'SVM', 'XGBOOST', 'DUMMY']}
    with pytest.raises(exporter.StopRun, match='RESULTS_NOT_EMPTY'):                                # el trabajador nunca sobrescribe
        exporter.worker(args)


# ---------------------------------------------------------------- 5. orquestador: Git, SHA-256 y montajes
@pytest.fixture
def never_docker(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('no debía llegar a Docker')
    monkeypatch.setattr(subprocess, 'run', refuse)


def run_main(capsys, converted, results, *extra):
    reference = Path(results).parent / 'referencia-vacia.json'
    reference.write_text('{}', encoding='utf-8')
    code = exporter.main(['--input', str(converted), '--results', str(results), '--image', 'riesgo-escolar-api:prueba',
                          '--reference', str(reference), *extra])
    return code, capsys.readouterr().out


def test_results_inside_a_git_work_tree_are_refused_and_nothing_is_created(converted, tmp_path, capsys, never_docker):
    repo = tmp_path / 'repo'
    (repo / '.git').mkdir(parents=True)
    code, out = run_main(capsys, converted, repo / 'salida')
    assert code == 2 and 'RESULTS_INSIDE_GIT' in out and not (repo / 'salida').exists()


def test_results_folder_must_be_empty(converted, tmp_path, capsys, never_docker):
    (tmp_path / 'ocupada').mkdir()
    (tmp_path / 'ocupada' / 'algo.txt').write_text('x', encoding='utf-8')
    code, out = run_main(capsys, converted, tmp_path / 'ocupada')
    assert code == 2 and 'RESULTS_NOT_EMPTY' in out


@pytest.mark.parametrize('name', ['cortes.csv', 'cierres.csv'])
def test_inputs_whose_sha256_differs_from_the_conversion_summary_are_refused(converted, tmp_path, capsys, never_docker, name):
    copy = tmp_path / 'copia'
    copy.mkdir()
    for item in converted.iterdir():
        (copy / item.name).write_bytes(item.read_bytes())
    (copy / name).write_bytes((copy / name).read_bytes() + b'\n')
    code, out = run_main(capsys, copy, tmp_path / 'salida')
    assert code == 2 and 'INPUT_HASH_MISMATCH' in out and name in out and not (tmp_path / 'salida').exists()


def test_inputs_inside_git_and_missing_image_are_refused(converted, tmp_path, capsys, never_docker):
    repo = tmp_path / 'repo'
    (repo / '.git').mkdir(parents=True)
    copy = repo / 'entrada'
    copy.mkdir()
    for item in converted.iterdir():
        (copy / item.name).write_bytes(item.read_bytes())
    code, out = run_main(capsys, copy, tmp_path / 'salida')
    assert code == 2 and 'INPUT_INSIDE_GIT' in out
    assert exporter.main(['--input', str(converted), '--results', str(tmp_path / 'otra')]) == 2 and 'IMAGE_REQUIRED' in capsys.readouterr().out


def test_the_worker_container_has_no_network_read_only_inputs_and_only_the_results_writable(tmp_path):
    command = exporter.docker_command('riesgo-escolar-api:prueba', tmp_path / 'in', tmp_path / 'out', tmp_path / 'ref.json')
    assert command[:3] == ['docker', 'run', '--rm'] and command[command.index('--network') + 1] == 'none' and '--cap-drop' in command
    mounts = [command[index + 1] for index, item in enumerate(command) if item == '--mount']
    targets = {mount.split('target=')[1].split(',')[0]: mount.endswith(',readonly') for mount in mounts}
    assert targets == {'/app/app': True, '/work/infra': True, '/input': True, '/reference/resumen.json': True, '/results': False}
    assert command[command.index('--entrypoint') + 1] == 'python' and '--worker' in command and 'riesgo-escolar-api:prueba' in command
    environment = [command[index + 1] for index, item in enumerate(command) if item == '-e']
    assert environment == ['PYTHONDONTWRITEBYTECODE=1', 'PYTHONPATH=/app:/work/infra', 'PYTHONWARNINGS=ignore::FutureWarning']          # ninguna credencial entra al contenedor


def test_sav_mode_without_pyreadstat_stops_with_a_stable_code(tmp_path, capsys):
    try:
        import pyreadstat  # noqa: F401
    except ImportError:
        assert exporter.main(['--sav-only', '--results', str(tmp_path)]) == 2 and 'PYREADSTAT_MISSING' in capsys.readouterr().out
    else:
        pytest.skip('pyreadstat disponible: se comprueba con el entorno de SPSS')
