"""Exportación para SPSS (Bloque 7): métricas por repetición y predicciones fuera de muestra del estudio REAL.

No cambia ningún resultado: repite, en memoria y sin base de datos, la comparación institucional que ya hizo la corrida real (mismo conjunto de
datos, semilla 0, 5 pliegues, 20 repeticiones) y recoge lo que `compare_institutional` calcula por repetición. Después comprueba que lo exportado
reproduce el resumen publicado de la corrida con la regla activa RIESGO_V2 (`tests/evidence/mejoras-08-resumen-agregado-v2.json`, ADR 013)
con tolerancia 1e-12. Además exporta la base por estudiante y bimestre y la base pareada B1/B2 (insumos al corte y al cierre, puntaje V2).

    <python del backend> infra/export_spss.py --input <carpeta del conversor> --results <carpeta FUERA de Git> --image riesgo-escolar-api:<etiqueta>
                         [--evidence tests/evidence/mejoras-07-verificacion-export.json] [--spss-python <python.exe con pyreadstat>]

Tres modos (el mismo archivo):
  (por defecto)  orquestador: verifica las entradas (SHA-256 contra resumen_conversion.json, como run_real_study.py), se niega a escribir dentro de
                 Git, ejecuta el trabajador dentro de la imagen de la API (sin red, entradas de solo lectura) y, si hay --spss-python, crea los .sav.
  --worker       lo que corre dentro del contenedor: construye el Dataset desde cortes.csv y cierres.csv, compara, exporta y verifica.
  --sav-only     convierte los CSV exportados a .sav con pyreadstat (entorno aparte, fuera del repositorio; no es dependencia del backend).

Salida de consola: solo conteos y estados; jamás códigos de estudiantes ni nombres. Los archivos con filas por estudiante van a --results.
"""
import argparse
import csv
from datetime import date, datetime, time, timezone
import hashlib
import json
import numbers
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'backend'))
try:
    import run_real_study as runner
    from run_real_study import StopRun
except ImportError:                                  # entorno de pyreadstat: solo --sav-only
    runner = None

    class StopRun(Exception):
        def __init__(self, code, detail=None, exit_code=2):
            super().__init__(code)
            self.code, self.detail, self.exit_code = code, detail, exit_code

LIMA = ZoneInfo('America/Lima')
SEED, REPETITIONS, FOLDS = 0, 20, 5
TOLERANCE = 1e-12
PLACEHOLDER_PERIOD = '00000000-0000-0000-0000-000000000000'    # solo para armar el protocolo en memoria; no se guarda
ORDER = ('RANDOM_FOREST', 'SVM', 'XGBOOST', 'DUMMY')
SUFFIX = {'RANDOM_FOREST': 'rf', 'SVM': 'svm', 'XGBOOST': 'xgb', 'DUMMY': 'dummy'}
MODEL_LABELS = {'RANDOM_FOREST': 'Random Forest', 'SVM': 'SVM', 'XGBOOST': 'XGBoost', 'DUMMY': 'Dummy (clase mayoritaria)'}
METRIC_LABELS = (('acc', 'Exactitud'), ('balacc', 'Exactitud balanceada'), ('f1', 'F1 macro'),
                 ('kappa', 'Kappa de Cohen (riesgo de referencia vs. predicho)'), ('recallhigh', 'Sensibilidad de la clase Alto'),
                 ('det', 'Detección total (Medio o Alto marcados Medio o Alto)'), ('fa', 'Falsa alarma total (Bajo marcado Medio o Alto)'))
# Dónde está cada métrica en el resumen publicado.
PUBLISHED = {'acc': ('accuracy',), 'balacc': ('balanced_accuracy',), 'f1': ('macro_f1',), 'kappa': ('cohen_kappa',),
             'recallhigh': ('recall_high',), 'det': ('detection', 'total', 'detection'), 'fa': ('detection', 'total', 'low_flagged')}
METRICS_FILE, PREDICTIONS_FILE = 'Metricas_por_repeticion', 'Predicciones_fuera_de_muestra'
STUDENT_FILE, PAIRED_FILE = 'Base_estudiante_bimestre', 'Base_pareada_B1_B2'
VARIABLES_FILE, VERIFICATION_FILE = 'variables.json', 'verificacion.json'
RISK_LABELS = {1: 'Bajo', 2: 'Medio', 3: 'Alto'}
try:
    from app.services.risk_reference import ACTIVE_RULE_VERSION
except ImportError:                                  # entorno de pyreadstat (--sav-only): no la necesita
    ACTIVE_RULE_VERSION = 'RIESGO_V2'
MAX_POINTS = {'RIESGO_V1': 10, 'RIESGO_V2': 8}
ORDINALS = {1: 'Primer', 2: 'Segundo', 3: 'Tercer', 4: 'Cuarto'}


# ---------------------------------------------------------------- colector
class Collector:
    """Guarda cada `RepetitionRecord` que entrega `compare_institutional`."""

    def __init__(self):
        self.records = []

    def __call__(self, record):
        self.records.append(record)


# ---------------------------------------------------------------- tablas (funciones puras)
def metric_columns() -> list[str]:
    return ['repeticion'] + [f'{metric}_{SUFFIX[model]}' for metric, _ in METRIC_LABELS for model in ORDER]


def metrics_table(records) -> list[dict]:
    """Una fila por repetición: las siete métricas de los cuatro modelos, exactamente lo que ya calculó la comparación."""
    from app.ml.institutional import detection_rates
    rows = {}
    for record in records:
        suffix = SUFFIX[record.algorithm]
        rates = detection_rates(record.detection['TOTAL'])
        rows.setdefault(record.repetition, {'repeticion': record.repetition + 1}).update({
            f'acc_{suffix}': record.metrics['accuracy'], f'balacc_{suffix}': record.metrics['balanced_accuracy'],
            f'f1_{suffix}': record.metrics['macro']['f1'], f'kappa_{suffix}': record.kappa,
            f'recallhigh_{suffix}': record.metrics['per_class']['HIGH']['recall'],
            f'det_{suffix}': rates['detection'], f'fa_{suffix}': rates['low_flagged']})
    columns = metric_columns()
    ordered = [rows[key] for key in sorted(rows)]
    if not ordered or any(set(columns) - set(row) for row in ordered):
        raise StopRun('METRICS_INCOMPLETE')
    return [{column: row[column] for column in columns} for row in ordered]


def modal_class(matrix: np.ndarray):
    """Clase más frecuente por columna de una matriz (repeticiones × filas) de clases 0–2. Empate → la de mayor riesgo.

    Devuelve (clase modal, repeticiones en que se predijo, hay empate).
    """
    counts = np.stack([(matrix == value).sum(axis=0) for value in range(3)])
    best = counts.max(axis=0)
    tied = (counts == best).sum(axis=0) > 1
    return 2 - np.argmax(counts[::-1], axis=0), best, tied


PREDICTION_COLUMNS = ['codigo', 'seccion', 'bimestre', 'riesgo_ref', 'riesgo_pred_rf', 'riesgo_pred_svm', 'riesgo_pred_xgb', 'riesgo_pred_dummy',
                      'acuerdo_rf', 'riesgo_pred_rf_rep1', 'detectado_rf', 'falsa_alarma_rf']


def predictions_table(records, sections: dict, bimesters: dict):
    """Una fila por estudiante y bimestre. `sections` {código: letra}; `bimesters` {código de bimestre: número}.

    Devuelve (filas, empates por modelo, número de repeticiones).
    """
    by_model, shared = {}, None
    for record in records:
        by_model.setdefault(record.algorithm, {})[record.repetition] = record.predictions
        current = (record.reference, record.keys, record.bimesters)
        if shared is None:
            shared = current
        elif not (np.array_equal(shared[0], current[0]) and shared[1] == current[1] and shared[2] == current[2]):
            raise StopRun('RECORDS_INCONSISTENT')
    if shared is None or set(by_model) != set(ORDER):
        raise StopRun('RECORDS_INCOMPLETE')
    reference, keys, codes = shared
    matrices = {model: np.stack([by_model[model][index] for index in sorted(by_model[model])]) for model in ORDER}
    repetitions = {matrix.shape[0] for matrix in matrices.values()}
    if len(repetitions) != 1:
        raise StopRun('RECORDS_INCOMPLETE')
    repetitions = repetitions.pop()
    modal, agreement, ties = {}, {}, {}
    for model in ORDER:
        modal[model], agreement[model], tied = modal_class(matrices[model])
        ties[model] = int(tied.sum())
    letters, rows = section_numbers(sections), []
    for index, (code, _) in enumerate(keys):
        reference_class, rf_class = int(reference[index]) + 1, int(modal['RANDOM_FOREST'][index]) + 1
        at_risk, flagged = reference_class >= 2, rf_class >= 2
        rows.append({'codigo': code, 'seccion': letters[sections[code]], 'bimestre': bimesters[codes[index]], 'riesgo_ref': reference_class,
                     **{f'riesgo_pred_{SUFFIX[model]}': int(modal[model][index]) + 1 for model in ORDER},
                     'acuerdo_rf': float(agreement['RANDOM_FOREST'][index]) / repetitions,
                     'riesgo_pred_rf_rep1': int(matrices['RANDOM_FOREST'][0][index]) + 1,
                     'detectado_rf': (int(flagged) if at_risk else None), 'falsa_alarma_rf': (None if at_risk else int(flagged))})
    return rows, ties, repetitions


def section_numbers(sections: dict) -> dict:
    return {letter: number for number, letter in enumerate(sorted(set(sections.values())), start=1)}


def bimester_label(number: int) -> str:
    return f'{ORDINALS[number]} bimestre' if number in ORDINALS else f'Bimestre {number}'


STUDENT_COLUMNS = ['codigo', 'seccion', 'bimestre', 'nota_corte', 'asist_corte', 'activ_corte', 'incid_corte', 'promedio', 'asistencia', 'entrega',
                   'incidencias', 'puntos_riesgo', 'riesgo_ref']
PAIRED_MEASURES = ('promedio', 'asistencia', 'entrega', 'incidencias', 'puntos_riesgo', 'riesgo_ref')


def two_places(value):
    from decimal import Decimal, ROUND_HALF_UP
    return None if value in (None, '') else Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def percent(numerator: int, denominator: int):
    """100 × numerador ÷ denominador con 2 decimales (mitad hacia arriba), de 0 a 100."""
    from decimal import Decimal, ROUND_HALF_UP
    return (Decimal(100 * numerator) / Decimal(denominator)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def student_tables(cut_rows, close_rows, calendar: dict, sections: dict, rule=None):
    """Base por estudiante y bimestre y base pareada, desde cortes.csv y cierres.csv con la regla activa (sin participación).

    `calendar` {código de bimestre: {'close': fecha de cierre, …}}. Devuelve (filas por estudiante y bimestre, filas pareadas).
    """
    from app.services.risk_reference import ClosingInputs, compute
    from decimal import Decimal
    rule = rule or ACTIVE_RULE_VERSION
    numbers_of = {code: number for number, code in enumerate(calendar, start=1)}
    by_close = {item['close'].isoformat(): code for code, item in calendar.items()}
    closings = {(row['student_code'], row['closing_date']): row for row in close_rows}
    letters, rows = section_numbers(sections), []
    for cut in sorted(cut_rows, key=lambda row: (row['student_code'], numbers_of[by_close[row['target_date']]])):
        close = closings.get((cut['student_code'], cut['target_date']))
        if close is None:
            raise StopRun('CLOSING_NOT_FOUND_FOR_CUT')
        scheduled, attended = int(close['days_scheduled']), int(close['days_attended'])
        planned, delivered = int(close['activities_scheduled']), int(close['activities_delivered'])
        result = compute(rule, ClosingInputs(Decimal(close['average_grade']), scheduled, attended, planned, delivered, None,
                                             int(close['behavior_incidents'])))
        rows.append({'codigo': cut['student_code'], 'seccion': letters[sections[cut['student_code']]],
                     'bimestre': numbers_of[by_close[cut['target_date']]], 'nota_corte': two_places(cut['average_grade']),
                     'asist_corte': two_places(cut['attendance_pct']), 'activ_corte': two_places(cut['activities_pct']),
                     'incid_corte': None if cut['behavior_incidents'] == '' else int(cut['behavior_incidents']),
                     'promedio': two_places(close['average_grade']), 'asistencia': percent(attended, scheduled),
                     'entrega': percent(delivered, planned), 'incidencias': int(close['behavior_incidents']),
                     'puntos_riesgo': result.total_points, 'riesgo_ref': ('LOW', 'MEDIUM', 'HIGH').index(result.risk_level) + 1})
    paired = {}
    for row in rows:
        item = paired.setdefault(row['codigo'], {'codigo': row['codigo'], 'seccion': row['seccion']})
        item.update({f'{measure}_b{row["bimestre"]}': row[measure] for measure in PAIRED_MEASURES})
    columns = paired_columns(len(calendar))
    if any(set(columns) - set(item) for item in paired.values()):
        raise StopRun('PAIRED_ROW_INCOMPLETE')
    return rows, [{column: item[column] for column in columns} for item in paired.values()]


def paired_columns(bimesters: int) -> list[str]:
    return ['codigo', 'seccion'] + [f'{measure}_b{number}' for measure in PAIRED_MEASURES for number in range(1, bimesters + 1)]


# ---------------------------------------------------------------- variables (etiquetas, valores y nivel de medida para SPSS)
def variable(name, label, measure, kind='numeric', values=None, display=None):
    return {'nombre': name, 'etiqueta': label, 'medida': measure, 'tipo': kind, 'valores': values, 'formato': display}


def table_specs(sections: dict, calendar_codes: list[str], repetitions: int) -> dict:
    metrics = [variable('repeticion', 'Repetición de la validación cruzada agrupada', 'scale', display='F8.0')]
    for metric, label in METRIC_LABELS:
        for model in ORDER:
            metrics.append(variable(f'{metric}_{SUFFIX[model]}', f'{label} - {MODEL_LABELS[model]}', 'scale', display='F8.4'))
    risk = {str(key): value for key, value in RISK_LABELS.items()}
    predicted = f'Riesgo predicho fuera de muestra (clase modal de {repetitions} repeticiones)'
    predictions = [
        variable('codigo', 'Código anónimo del estudiante (Excel)', 'nominal', kind='string'),
        variable('seccion', 'Sección', 'nominal', values={str(number): letter for letter, number in section_numbers(sections).items()}, display='F8.0'),
        variable('bimestre', 'Bimestre del corte intermedio', 'nominal',
                 values={str(number): bimester_label(number) for number in range(1, len(calendar_codes) + 1)}, display='F8.0'),
        variable('riesgo_ref', f'Riesgo de referencia al cierre ({ACTIVE_RULE_VERSION})', 'ordinal', values=risk, display='F8.0'),
        *[variable(f'riesgo_pred_{SUFFIX[model]}', f'{predicted} - {MODEL_LABELS[model]}', 'ordinal', values=risk, display='F8.0') for model in ORDER],
        variable('acuerdo_rf', f'Proporción de las {repetitions} repeticiones en que Random Forest predijo su clase modal', 'scale', display='F8.4'),
        variable('riesgo_pred_rf_rep1', 'Riesgo predicho fuera de muestra - Random Forest, repetición 1', 'ordinal', values=risk, display='F8.0'),
        variable('detectado_rf', 'Caso Medio o Alto detectado por Random Forest (clase modal); vacío si la referencia es Bajo', 'nominal',
                 values={'0': 'No detectado', '1': 'Detectado'}, display='F8.0'),
        variable('falsa_alarma_rf', 'Caso Bajo marcado Medio o Alto por Random Forest (clase modal); vacío si la referencia es Medio o Alto', 'nominal',
                 values={'0': 'Sin falsa alarma', '1': 'Falsa alarma'}, display='F8.0')]
    sections_values = {str(number): letter for letter, number in section_numbers(sections).items()}
    bimester_values = {str(number): bimester_label(number) for number in range(1, len(calendar_codes) + 1)}
    points = f'Puntaje {ACTIVE_RULE_VERSION} al cierre (0-{MAX_POINTS[ACTIVE_RULE_VERSION]})'
    measures = {'promedio': ('Promedio de notas al cierre (0-20)', 'scale', None, 'F8.2'),
                'asistencia': ('Asistencia al cierre (%)', 'scale', None, 'F8.2'),
                'entrega': ('Entrega de actividades al cierre (%)', 'scale', None, 'F8.2'),
                'incidencias': ('Incidencias al cierre', 'scale', None, 'F8.0'),
                'puntos_riesgo': (points, 'scale', None, 'F8.0'),
                'riesgo_ref': (f'Riesgo de referencia al cierre ({ACTIVE_RULE_VERSION})', 'ordinal', risk, 'F8.0')}
    student = [
        variable('codigo', 'Código anónimo del estudiante (Excel)', 'nominal', kind='string'),
        variable('seccion', 'Sección', 'nominal', values=sections_values, display='F8.0'),
        variable('bimestre', 'Bimestre', 'nominal', values=bimester_values, display='F8.0'),
        variable('nota_corte', 'Promedio de notas parciales al corte (0-20)', 'scale', display='F8.2'),
        variable('asist_corte', 'Asistencia al corte (%)', 'scale', display='F8.2'),
        variable('activ_corte', 'Entrega de actividades al corte (%)', 'scale', display='F8.2'),
        variable('incid_corte', 'Incidencias al corte', 'scale', display='F8.0'),
        *[variable(name, label, measure, values=values, display=fmt) for name, (label, measure, values, fmt) in measures.items()]]
    paired = [variable('codigo', 'Código anónimo del estudiante (Excel)', 'nominal', kind='string'),
              variable('seccion', 'Sección', 'nominal', values=sections_values, display='F8.0')]
    for name in PAIRED_MEASURES:
        label, measure, values, fmt = measures[name]
        paired += [variable(f'{name}_b{number}', f'{label} - {bimester_label(number)}', measure, values=values, display=fmt)
                   for number in range(1, len(calendar_codes) + 1)]
    return {METRICS_FILE: {'etiqueta': 'Métricas por repetición (CV agrupada, estudio REAL local)',
                           'variables': metrics},
            STUDENT_FILE: {'etiqueta': f'Base por estudiante y bimestre ({ACTIVE_RULE_VERSION}, REAL local)', 'variables': student},
            PAIRED_FILE: {'etiqueta': f'Base pareada B1-B2 por estudiante ({ACTIVE_RULE_VERSION}, REAL local)', 'variables': paired},
            PREDICTIONS_FILE: {'etiqueta': 'Predicciones fuera de muestra por estudiante y bimestre',
                               'variables': predictions}}


# ---------------------------------------------------------------- archivos
def cell(value) -> str:
    if value is None:
        return ''
    if isinstance(value, numbers.Integral):
        return str(int(value))
    if isinstance(value, numbers.Real):
        value = float(value)
        return '' if value != value else repr(value)
    return str(value)


def write_csv(path: Path, columns: list[str], rows: list[dict]):
    with Path(path).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\r\n')
        writer.writerow(columns)
        writer.writerows([[cell(row[column]) for column in columns] for row in rows])


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- Dataset sin base de datos
def build_dataset(inputs):
    """El mismo Dataset que `institutional_study.build_dataset`, armado desde cortes.csv y cierres.csv (sin base de datos).

    Mismas reglas: características del corte (sin participación), etiqueta = nivel de la regla del protocolo (RIESGO_V2, activa) calculado con los
    insumos de cierre sin participación, grupo = código del
    estudiante, y las mismas exclusiones (sin referencia o con ausencias que no admite la inferencia). Los identificadores internos se derivan de los
    hashes de las entradas: no afectan a particiones ni métricas.
    """
    from app.ml.features import Dataset, Label, Observation
    from app.services.csv_validation import parse_csv as parse_cortes
    from app.services.institutional_study import GENERATOR, csv_scales, feature_config
    from app.services.processing_protocol import params_of
    from app.services.risk_reference import ClosingInputs, compute
    from decimal import Decimal
    params = params_of(SimpleNamespace(**inputs.protocol(PLACEHOLDER_PERIOD)))
    config = feature_config(params)
    period = SimpleNamespace(start_date=date(inputs.year, 1, 1), end_date=date(inputs.year, 12, 31))
    parsed = parse_cortes(inputs.cortes, period, csv_scales(params))
    if parsed.errors:
        raise StopRun('CORTES_INVALID', str(len(parsed.errors)))
    namespace = hashlib.sha256(inputs.cortes + inputs.cierres).hexdigest()
    closings = {}
    for row in inputs.close_rows:
        available = datetime.fromisoformat(row['closing_available_at'])
        if available.tzinfo is None:
            raise StopRun('CLOSING_WITHOUT_TIMEZONE')
        closings[(row['student_code'], date.fromisoformat(row['closing_date']))] = (
            ClosingInputs(Decimal(row['average_grade']), int(row['days_scheduled']), int(row['days_attended']), int(row['activities_scheduled']),
                          int(row['activities_delivered']), None, int(row['behavior_incidents'])),          # V2: la participación no se lee
            date.fromisoformat(row['closing_date']), available)
    exclusions, observations, labels = {}, [], []

    def drop(reason):
        exclusions[reason] = exclusions.get(reason, 0) + 1
    for row in parsed.rows:
        values = {name: float(row[name]) if row[name] is not None else None for name in config.features}
        reference = closings.get((row['student_code'], row['target_date']))
        if reference is None:
            drop('NO_REFERENCE')
        elif (any(values[name] is None for name in config.required_features) or
              sum(v is None for v in values.values()) / len(values) > config.inference_max_missing_fraction):
            drop('INFERENCE_ABSTENTION')
        else:
            closing_inputs, closing_date, available = reference
            snapshot = uuid5(NAMESPACE_URL, f'export-spss:{namespace}:snapshot:{row["student_code"]}:{row["cutoff_at"].isoformat()}')
            observations.append(Observation(student_key=row['student_code'], snapshot_id=snapshot,
                enrollment_id=uuid5(NAMESPACE_URL, f'export-spss:{namespace}:enrollment:{row["student_code"]}'),
                period_id=uuid5(NAMESPACE_URL, f'export-spss:{namespace}:period'), data_origin='REAL', schema_version='academic-v1', revision=1,
                supersedes_id=None, window_start=row['window_start'], available_at=row['available_at'], cutoff_at=row['cutoff_at'],
                target_date=row['target_date'], created_at=row['cutoff_at'], eligible=True, values=values,
                feature_available_at={name: row['available_at'] for name in config.features}, input_provenance='snapshot:' + str(snapshot)))
            labels.append(Label(snapshot_id=snapshot, risk=compute(config.criterion_version, closing_inputs).risk_level, criterion_version=config.criterion_version,
                outcome_definition=config.criterion_definition, provenance=f'risk_reference:{snapshot}',
                observed_at=datetime.combine(closing_date, time(0, 0), tzinfo=LIMA), available_at=available))
    if not observations:
        raise StopRun('INSUFFICIENT_DATA_FOR_STUDY')
    as_of = max([label.available_at for label in labels] + [row.created_at for row in observations])
    return Dataset(schema_version='ml-dataset-v1', scope='INSTITUTIONAL', provenance=f'{GENERATOR}:export-spss', evaluation_as_of=as_of,
                   config=config, observations=observations, labels=labels), exclusions


# ---------------------------------------------------------------- verificación
def spread_of(values) -> dict:
    array = np.asarray(values, dtype=float)
    return {'mean': float(array.mean()), 'sd': float(array.std(ddof=1)) if len(array) > 1 else None}


def published_spread(models: dict, model: str, metric: str) -> dict:
    node = models[model]
    for part in PUBLISHED[metric]:
        node = node[part]
    return node


def verify_exports(results: Path, reference: dict, report: dict, calendar_codes: list[str], ties: dict, tolerance=TOLERANCE) -> dict:
    """Vuelve a leer los CSV exportados y compara con el resumen publicado y con el informe de la comparación en proceso."""
    from app.ml.institutional import cohen_kappa
    metric_rows, prediction_rows = read_csv(results / f'{METRICS_FILE}.csv'), read_csv(results / f'{PREDICTIONS_FILE}.csv')
    models = reference['comparison']['models']
    differences, by_model, largest = [], {}, 0.0
    for model in ORDER:
        by_model[model] = {}
        for metric, _ in METRIC_LABELS:
            column = f'{metric}_{SUFFIX[model]}'
            if any(row[column] == '' for row in metric_rows):
                raise StopRun('METRIC_NOT_ESTIMABLE', column)
            recomputed, published = spread_of([float(row[column]) for row in metric_rows]), published_spread(models, model, metric)
            item = {'media': recomputed['mean'], 'sd': recomputed['sd'], 'publicado_media': published['mean'], 'publicado_sd': published['sd'],
                    'dif_media': abs(recomputed['mean'] - published['mean']), 'dif_sd': abs(recomputed['sd'] - published['sd'])}
            by_model[model][metric] = item
            largest = max(largest, item['dif_media'], item['dif_sd'])
            differences += [{'modelo': model, 'metrica': metric, 'estadistico': stat, 'dif': item[f'dif_{stat}']}
                            for stat in ('media', 'sd') if item[f'dif_{stat}'] > tolerance]
    in_process = all(abs(by_model[model][metric][key] - in_process_spread(report['algorithms'][model], metric)[stat]) <= tolerance
                     for model in ORDER for metric, _ in METRIC_LABELS for key, stat in (('media', 'mean'), ('sd', 'sd')))
    bimester_of = {str(number): code for number, code in enumerate(calendar_codes, start=1)}
    distribution = {code: [sum(1 for row in prediction_rows if row['bimestre'] == number and row['riesgo_ref'] == str(level)) for level in (1, 2, 3)]
                    for number, code in bimester_of.items()}
    published_distribution = reference.get('reference_distribution_low_medium_high', {})
    rf_modal = {}
    for scope in ['TOTAL', *calendar_codes]:
        rows = [row for row in prediction_rows if scope == 'TOTAL' or bimester_of[row['bimestre']] == scope]
        at_risk = [row for row in rows if row['detectado_rf'] != '']
        low = [row for row in rows if row['falsa_alarma_rf'] != '']
        detected, flagged = sum(row['detectado_rf'] == '1' for row in at_risk), sum(row['falsa_alarma_rf'] == '1' for row in low)
        matrix = np.zeros((3, 3), dtype=int)
        for row in rows:
            matrix[int(row['riesgo_ref']) - 1][int(row['riesgo_pred_rf']) - 1] += 1
        rf_modal[scope] = {'filas': len(rows), 'en_riesgo': len(at_risk), 'detectados': detected,
                           'deteccion': detected / len(at_risk) if at_risk else None, 'referencia_bajo': len(low), 'falsas_alarmas': flagged,
                           'falsa_alarma': flagged / len(low) if low else None, 'kappa_referencia_vs_modal': cohen_kappa(matrix),
                           'matriz_referencia_por_clase_modal': {'filas_referencia_columnas_predicho': ['Bajo', 'Medio', 'Alto'],
                                                                 'conteos': matrix.tolist()}}
    published_rf = {scope: {'deteccion_media': models['RANDOM_FOREST']['detection'][key]['detection']['mean'],
                            'falsa_alarma_media': models['RANDOM_FOREST']['detection'][key]['low_flagged']['mean']}
                    for scope, key in [('TOTAL', 'total'), *[(code, code) for code in calendar_codes]]}
    checks = {'regla_del_resumen_publicado': reference.get('risk_rule') == ACTIVE_RULE_VERSION,
              'metricas_dentro_de_tolerancia': not differences,
              'filas_metricas': len(metric_rows) == reference['comparison']['repetitions'],
              'filas_predicciones': len(prediction_rows) == reference['comparison']['observations'],
              'estudiantes': len({row['codigo'] for row in prediction_rows}) == reference['comparison']['students'],
              'distribucion_referencia': distribution == published_distribution,
              'coincide_con_informe_en_proceso': in_process}
    return {'filas': {'metricas': len(metric_rows), 'predicciones': len(prediction_rows),
                      'estudiantes': len({row['codigo'] for row in prediction_rows})},
            'tolerancia': tolerance, 'maxima_diferencia_absoluta': largest, 'metricas_vs_publicado': by_model,
            'distribucion_referencia_bajo_medio_alto': {'exportada': distribution, 'publicada': published_distribution},
            'empates_clase_modal_por_modelo': ties,
            'rf_clase_modal': rf_modal, 'rf_promedio_por_repeticion_publicado': published_rf,
            'comprobaciones': checks, 'diferencias': differences, 'reproduce_resumen_publicado': all(checks.values())}


def verify_student_tables(results: Path, expected_levels: dict, calendar_codes: list[str]) -> dict:
    """Vuelve a leer las dos bases y comprueba filas, estudiantes, coherencia puntaje → nivel V2 y distribución esperada (calculada)."""
    from app.services.risk_reference import level_of_v2
    student, paired = read_csv(results / f'{STUDENT_FILE}.csv'), read_csv(results / f'{PAIRED_FILE}.csv')
    predictions = read_csv(results / f'{PREDICTIONS_FILE}.csv')
    levels = ('LOW', 'MEDIUM', 'HIGH')
    distribution = {code: [sum(1 for row in student if row['bimestre'] == str(number) and row['riesgo_ref'] == str(level)) for level in (1, 2, 3)]
                    for number, code in enumerate(calendar_codes, start=1)}
    expected = {code: [expected_levels[code][level] for level in levels] for code in calendar_codes}
    coherent = all(levels.index(level_of_v2(int(row['puntos_riesgo']))) + 1 == int(row['riesgo_ref']) for row in student)
    in_range = all(0 <= int(row['puntos_riesgo']) <= MAX_POINTS[ACTIVE_RULE_VERSION] for row in student) and all(
        0 <= float(row[name]) <= 100 for row in student for name in ('asistencia', 'entrega'))
    same_as_predictions = [(row['codigo'], row['bimestre'], row['riesgo_ref']) for row in student] == [
        (row['codigo'], row['bimestre'], row['riesgo_ref']) for row in predictions]
    paired_match = all(
        all(item[f'{name}_b{row["bimestre"]}'] == row[name] for name in PAIRED_MEASURES)
        for item in paired for row in student if row['codigo'] == item['codigo'])
    checks = {'filas_base_estudiante': len(student) == len(predictions), 'filas_base_pareada': len(paired) == len({r['codigo'] for r in student}),
              'puntaje_coherente_con_nivel': coherent, 'rangos_validos': in_range, 'distribucion_esperada_calculada': distribution == expected,
              'misma_referencia_que_predicciones': same_as_predictions, 'pareada_coincide_con_base_estudiante': paired_match,
              'sin_columna_de_participacion': not any('particip' in name for name in [*student[0], *paired[0]])}
    return {'filas': {'base_estudiante_bimestre': len(student), 'base_pareada': len(paired)},
            'distribucion_referencia_v2': {'exportada': distribution, 'esperada_conversor': expected},
            'comprobaciones': checks}


def in_process_spread(algorithm_report: dict, metric: str) -> dict:
    """La misma métrica tal como la resume la comparación en proceso (`repeated_cv` y detección total)."""
    cv, total = algorithm_report['repeated_cv'], algorithm_report['detection']['total']
    return {'acc': cv['accuracy'], 'balacc': cv['balanced_accuracy'], 'f1': cv['macro']['f1'], 'kappa': cv['cohen_kappa'],
            'recallhigh': cv['per_class']['HIGH']['recall'], 'det': total['detection'], 'fa': total['low_flagged']}[metric]


# ---------------------------------------------------------------- modo trabajador (dentro del contenedor)
def worker(args) -> int:
    if runner is None:
        raise StopRun('RUNNER_UNAVAILABLE')
    from app.ml.institutional import compare_institutional
    from app.ml.train import versions
    results = Path(args.results)
    if not results.is_dir() or any(results.iterdir()):
        raise StopRun('RESULTS_NOT_EMPTY')
    reference = json.loads(Path(args.reference).read_text(encoding='utf-8'))
    inputs = runner.Inputs(args.input)
    print(f'entradas verificadas: {len(inputs.cut_rows)} cortes, {len(inputs.close_rows)} cierres, {len(inputs.codes)} estudiantes')
    dataset, exclusions = build_dataset(inputs)
    calendar_codes = list(inputs.calendar)
    expected = {code: [counts[level] for level in runner.LEVELS] for code, counts in inputs.expected_levels.items()}
    levels = {}
    by_snapshot = {label.snapshot_id: label.risk for label in dataset.labels}
    for row in dataset.observations:
        bimester = next(code for code, item in inputs.calendar.items() if item['close'] == row.target_date)
        levels.setdefault(bimester, [0, 0, 0])[runner.LEVELS.index(by_snapshot[row.snapshot_id])] += 1
    if levels != expected and not exclusions:
        raise StopRun('LABELS_DIFFER_FROM_CONVERSION_SUMMARY')
    collector = Collector()
    study_id = uuid5(NAMESPACE_URL, 'export-spss:' + hashlib.sha256(inputs.cortes + inputs.cierres).hexdigest())
    print(f'comparación en proceso: {len(dataset.observations)} observaciones, semilla {SEED}, {FOLDS} pliegues, {REPETITIONS} repeticiones...')
    result = compare_institutional(dataset, seed=SEED, study_id=study_id, repetitions=REPETITIONS, requested_folds=FOLDS,
                                   bimesters={item['close']: code for code, item in inputs.calendar.items()}, collector=collector)
    sections = {row['student_code']: row['section'] for row in inputs.cut_rows}
    bimesters = {code: number for number, code in enumerate(calendar_codes, start=1)}
    metric_rows = metrics_table(collector.records)
    prediction_rows, ties, repetitions = predictions_table(collector.records, sections, bimesters)
    write_csv(results / f'{METRICS_FILE}.csv', metric_columns(), metric_rows)
    write_csv(results / f'{PREDICTIONS_FILE}.csv', PREDICTION_COLUMNS, prediction_rows)
    student_rows, paired_rows = student_tables(inputs.cut_rows, inputs.close_rows, inputs.calendar, sections)
    write_csv(results / f'{STUDENT_FILE}.csv', STUDENT_COLUMNS, student_rows)
    write_csv(results / f'{PAIRED_FILE}.csv', paired_columns(len(calendar_codes)), paired_rows)
    specs = table_specs(sections, calendar_codes, repetitions)
    (results / VARIABLES_FILE).write_text(json.dumps(specs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verification = verify_exports(results, reference, result.report, calendar_codes, ties)
    tables = verify_student_tables(results, inputs.expected_levels, calendar_codes)
    verification['comprobaciones'].update(tables['comprobaciones'])
    verification['filas'].update(tables['filas'])
    verification['distribucion_referencia_v2'] = tables['distribucion_referencia_v2']
    verification['reproduce_resumen_publicado'] = all(verification['comprobaciones'].values())
    verification = {'bloque': 8, 'regla': ACTIVE_RULE_VERSION, 'alcance': 'Solo agregados: sin códigos de estudiantes ni nombres.',
                    'parametros': {'semilla': SEED, 'repeticiones': REPETITIONS, 'pliegues': FOLDS, 'modelos': list(ORDER),
                                   'criterio_de_seleccion': result.report['selection_rule'], 'modelo_seleccionado': result.selected_algorithm},
                    'entradas': {'cortes_sha256': hashlib.sha256(inputs.cortes).hexdigest(), 'cierres_sha256': hashlib.sha256(inputs.cierres).hexdigest(),
                                 'filas_cortes': len(inputs.cut_rows), 'filas_cierres': len(inputs.close_rows)},
                    'exclusiones': exclusions, 'entorno': {'versiones': versions()}, **verification}
    (results / VERIFICATION_FILE).write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'exportado: {len(metric_rows)} filas de métricas, {len(prediction_rows)} de predicciones, {len(student_rows)} por estudiante y bimestre, '
          f'{len(paired_rows)} pareadas')
    print(f'reproduce_resumen_publicado: {verification["reproduce_resumen_publicado"]} (máxima diferencia {verification["maxima_diferencia_absoluta"]:.3e})')
    return 0


# ---------------------------------------------------------------- modo .sav (entorno con pyreadstat)
def sav_only(args) -> int:
    try:
        import pandas
        import pyreadstat
    except ImportError:
        raise StopRun('PYREADSTAT_MISSING') from None
    results = Path(args.results)
    specs = json.loads((results / VARIABLES_FILE).read_text(encoding='utf-8'))
    for name, table in specs.items():
        variables = table['variables']
        frame = pandas.read_csv(results / f'{name}.csv', encoding='utf-8-sig', float_precision='round_trip', keep_default_na=False, na_values=[''],
                                dtype={item['nombre']: str for item in variables if item['tipo'] == 'string'})
        labels = {item['nombre']: {float(key): value for key, value in item['valores'].items()} for item in variables if item['valores']}
        measures = {item['nombre']: item['medida'] for item in variables}
        formats = {item['nombre']: item['formato'] for item in variables if item['formato']}
        target = results / f'{name}.sav'
        pyreadstat.write_sav(frame, str(target), file_label=table['etiqueta'], column_labels=[item['etiqueta'] for item in variables],
                             variable_value_labels=labels, variable_measure=measures, variable_format=formats)
        again, meta = pyreadstat.read_sav(str(target))
        same = (list(again.columns) == list(frame.columns) and len(again) == len(frame) and list(meta.column_labels) == [i['etiqueta'] for i in variables]
                and all(np.array_equal(again[item['nombre']].to_numpy(dtype=float), frame[item['nombre']].to_numpy(dtype=float), equal_nan=True)
                        for item in variables if item['tipo'] != 'string')
                and all(again[item['nombre']].tolist() == frame[item['nombre']].tolist() for item in variables if item['tipo'] == 'string')
                and {key: {float(k): v for k, v in value.items()} for key, value in meta.variable_value_labels.items()} == labels
                and all(meta.variable_measure[key] == value for key, value in measures.items()))
        if not same:
            raise StopRun('SAV_READBACK_DIFFERS', name)
        print(f'{name}.sav: {len(frame)} filas, {len(variables)} variables, releído y coincide con el CSV')
    return 0


# ---------------------------------------------------------------- modo orquestador (Windows)
def docker_command(image: str, input_dir: Path, results: Path, reference: Path) -> list[str]:
    def mount(source, target, readonly=True):
        return ['--mount', f'type=bind,source={source},target={target}' + (',readonly' if readonly else '')]
    return ['docker', 'run', '--rm', '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/app:/work/infra', '-e', 'PYTHONWARNINGS=ignore::FutureWarning', '-w', '/app',
            *mount(ROOT / 'backend' / 'app', '/app/app'), *mount(HERE, '/work/infra'), *mount(Path(input_dir).resolve(), '/input'),
            *mount(Path(reference).resolve(), '/reference/resumen.json'), *mount(Path(results).resolve(), '/results', readonly=False),
            '--entrypoint', 'python', image, '/work/infra/export_spss.py', '--worker', '--input', '/input', '--results', '/results',
            '--reference', '/reference/resumen.json']


def orchestrate(args) -> int:
    if runner is None:
        raise StopRun('RUNNER_UNAVAILABLE')
    results = Path(args.results)
    if runner.converter.inside_git_tree(results):
        raise StopRun('RESULTS_INSIDE_GIT')
    if results.exists() and (not results.is_dir() or any(results.iterdir())):
        raise StopRun('RESULTS_NOT_EMPTY')
    reference = Path(args.reference)
    if not reference.is_file():
        raise StopRun('REFERENCE_MISSING')
    inputs = runner.Inputs(args.input)                       # ENTRADA fuera de Git y SHA-256 contra resumen_conversion.json
    print(f'entradas verificadas: {len(inputs.cut_rows)} cortes, {len(inputs.close_rows)} cierres, {len(inputs.codes)} estudiantes')
    results.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(docker_command(args.image, args.input, results, reference))
    if completed.returncode != 0:
        raise StopRun('WORKER_FAILED', str(completed.returncode), exit_code=3)
    image_id = subprocess.run(['docker', 'image', 'inspect', '--format', '{{.Id}}', args.image], capture_output=True, text=True).stdout.strip()
    sav = False
    if args.spss_python:
        spss = subprocess.run([args.spss_python, str(Path(__file__).resolve()), '--sav-only', '--results', str(results)])
        if spss.returncode != 0:
            raise StopRun('SAV_FAILED', str(spss.returncode), exit_code=3)
        sav = True
    else:
        print('SAV_NOT_GENERATED: sin --spss-python (solo CSV)')
    verification = json.loads((results / VERIFICATION_FILE).read_text(encoding='utf-8'))
    verification['fecha_ejecucion'] = datetime.now(timezone.utc).date().isoformat()
    verification['entorno'] |= {'imagen': args.image, 'imagen_id': image_id}
    verification['sav_generado'] = sav
    verification['archivos'] = {path.name: sha256_file(path) for path in sorted(results.iterdir())
                                if path.suffix in ('.csv', '.sav') or path.name == VARIABLES_FILE}
    text = json.dumps(verification, ensure_ascii=False, indent=2) + '\n'
    if any(code in text for code in inputs.codes):
        raise StopRun('VERIFICATION_CONTAINS_CODES', exit_code=3)
    (results / VERIFICATION_FILE).write_text(text, encoding='utf-8')
    if not verification['reproduce_resumen_publicado']:
        print('NO_REPRODUCE: no se escribe la evidencia del repositorio. Diferencias:')
        print(json.dumps(verification['diferencias'] or verification['comprobaciones'], ensure_ascii=False))
        return 4
    if args.evidence:
        Path(args.evidence).write_text(text, encoding='utf-8')
        print('evidencia escrita (solo agregados)')
    print('reproduce_resumen_publicado: True')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--image', help='imagen de la API con la que corrió el estudio, p. ej. riesgo-escolar-api:b62')
    parser.add_argument('--reference', type=Path, default=ROOT / 'tests' / 'evidence' / 'mejoras-08-resumen-agregado-v2.json')
    parser.add_argument('--evidence', type=Path, help='archivo de verificación (solo agregados) que se escribe si reproduce el resumen publicado')
    parser.add_argument('--spss-python', help='python.exe de un entorno aparte con pyreadstat y pandas, para crear los .sav')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--sav-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.sav_only:
            return sav_only(args)
        if args.input is None:
            raise StopRun('INPUT_REQUIRED')
        if args.worker:
            return worker(args)
        if not args.image:
            raise StopRun('IMAGE_REQUIRED')
        return orchestrate(args)
    except StopRun as stop:
        print(f'export_spss: DETENIDO {stop.code}' + (f' ({stop.detail})' if stop.detail else ''))
        return stop.exit_code


if __name__ == '__main__':
    sys.exit(main())
