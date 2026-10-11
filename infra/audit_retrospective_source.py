"""Read-only source audit using the bundled documentary Python/openpyxl.

No names, codes, academic rows, formulas or original workbook are written out.
This checks declarations in the workbook, not institutional authenticity.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile
from zoneinfo import ZoneInfo

import openpyxl

SOURCE_HASH = '9cd4243f420b6da5e4ddab629d239334cbe6f2c100642eb6c0ec7ae53243c862'
PACKAGE_HASH = '08ace0a90feb05e29d1ff5dedb6bd126139fd42ca85df06c5ef5802a70a86de4'
CUTS = {'B1': '2026-04-21', 'B2': '2026-06-30'}
FEATURES = ('promedio_parcial_0_20', 'asistencia_parcial_proporcion', 'entrega_parcial_proporcion')
CLASSES = ('Bajo', 'Medio', 'Alto')
LIMA = ZoneInfo('America/Lima')


def check(condition, code):
    if not condition:
        raise ValueError(code)


def dt(value):
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=LIMA) if parsed.tzinfo is None else parsed


def records(wb, sheet):
    iterator = iter(wb[sheet].values)
    keys = next(iterator)
    return [{key: row[i] if i < len(row) else None for i, key in enumerate(keys)}
            for row in iterator if any(v is not None for v in row)]


def audit(source, package):
    original = Path(source).read_bytes()
    archive_bytes = Path(package).read_bytes()
    check(hashlib.sha256(original).hexdigest() == SOURCE_HASH, 'SOURCE_HASH_MISMATCH')
    check(hashlib.sha256(archive_bytes).hexdigest() == PACKAGE_HASH, 'PACKAGE_HASH_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        derived_rows = list(csv.DictReader(io.StringIO(archive.read('base_derivada_sin_nombres.csv').decode('utf-8-sig'))))
    derived = {r['registro_id']: r for r in derived_rows}
    wb = openpyxl.load_workbook(io.BytesIO(original), read_only=True, data_only=True)
    try:
        base, grades = records(wb, 'Bimestres'), records(wb, 'Calificaciones')
        params = {r['Parametro']: r['Valor'] for r in records(wb, 'Parametros')}
        old_predictions, old_alerts = records(wb, 'Predicciones'), records(wb, 'Alertas')
    finally:
        wb.close()
    check(len(base) == len(derived) == 120 and len(grades) == 720, 'SOURCE_COUNTS_MISMATCH')
    check(len({r['registro_id'] for r in base}) == 120, 'DUPLICATE_SOURCE_RECORD')
    check(len({g['calificacion_id'] for g in grades}) == 720, 'DUPLICATE_GRADE')
    groups = defaultdict(list)
    for grade in grades:
        groups[grade['registro_id']].append(grade)
    check(set(groups) == set(derived) == {r['registro_id'] for r in base}, 'SOURCE_JOIN_MISMATCH')
    students = {term: set() for term in CUTS}
    rounding_changes = 0
    latest = {}
    def lower(value, high, medium):
        return 2 if value < high else 1 if value < medium else 0
    for row in base:
        term = row['bimestre']
        cut = dt(CUTS[term])
        close = dt(row['fecha_cierre'])
        partial_grades = groups[row['registro_id']]
        expected = derived[row['registro_id']]
        students[term].add(row['codigo_estudiante'])
        check(len(partial_grades) == 6 and len({v['curso'] for v in partial_grades}) == 6, 'SOURCE_COURSE_COUNT')
        check(dt(row['fecha_inicio']) <= cut < close, 'SOURCE_WINDOW_MISMATCH')
        for grade in partial_grades:
            check(grade['codigo_estudiante'] == row['codigo_estudiante'] and grade['bimestre'] == term, 'GRADE_JOIN_MISMATCH')
            check(dt(row['fecha_inicio']) <= dt(grade['fecha_evaluacion_parcial']) <= dt(grade['fecha_registro_parcial'])
                  <= dt(grade['fecha_disponible_parcial']) <= cut, 'GRADE_AFTER_CUTOFF')
            check(0 <= float(grade['nota_parcial_0_20']) <= 20, 'GRADE_OUT_OF_SCALE')
        for kind in ('asistencia', 'actividades'):
            check(dt(row['fecha_inicio']) <= dt(row[f'fecha_corte_{kind}']) <= dt(row[f'fecha_registro_{kind}'])
                  <= dt(row[f'fecha_disponible_{kind}']) <= cut, 'SOURCE_AFTER_CUTOFF')
        da, dp = row['dias_asistidos_al_corte'], row['dias_programados_al_corte']
        ae, ap = row['actividades_entregadas_al_corte'], row['actividades_programadas_al_corte']
        check(0 <= da <= dp and dp > 0 and 0 <= ae <= ap and ap > 0, 'SOURCE_INVALID_DENOMINATOR')
        check(da <= row['dias_asistidos'] and dp <= row['dias_programados']
              and ae <= row['actividades_entregadas'] and ap <= row['actividades_programadas'], 'SOURCE_PARTIAL_TOTAL_MISMATCH')
        mean = float(sum(Decimal(str(v['nota_parcial_0_20'])) for v in partial_grades) / 6)
        values = [mean, da / dp, ae / ap]
        check(all(math.isclose(values[i], float(expected[k]), rel_tol=0, abs_tol=1e-12) for i, k in enumerate(FEATURES)), 'DERIVED_FEATURE_MISMATCH')
        available = max([dt(v['fecha_disponible_parcial']) for v in partial_grades]
                        + [dt(row['fecha_disponible_asistencia']), dt(row['fecha_disponible_actividades'])])
        check(available == dt(expected['ultima_disponibilidad_predictores']), 'DERIVED_AVAILABILITY_MISMATCH')
        latest[term] = max(latest.get(term, available), available)
        reference = dt(row['fecha_referencia'])
        check(close <= reference == dt(expected['fecha_referencia_disponible']), 'SOURCE_REFERENCE_MISMATCH')
        if term == 'B1':
            check(reference < dt(CUTS['B2']), 'TRAIN_LABEL_AFTER_B2')
        final = (sum(Decimal(str(v['nota_0_20'])) for v in partial_grades) / 6).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        rounding_changes += float(final) != float(row['promedio_0_20'])
        points = lower(float(final), params['nota_alto_menor_que'], params['nota_medio_menor_que'])
        points += lower(row['dias_asistidos'] / row['dias_programados'], params['asistencia_alto_menor_que'], params['asistencia_medio_menor_que'])
        points += lower(row['actividades_entregadas'] / row['actividades_programadas'], params['entrega_alto_menor_que'], params['entrega_medio_menor_que'])
        points += 2 if row['participacion_1_5'] <= params['participacion_alto_maximo'] else 1 if row['participacion_1_5'] <= params['participacion_medio_maximo'] else 0
        points += 2 if row['numero_incidencias'] >= params['incidencias_alto_minimo'] else 1 if row['numero_incidencias'] >= params['incidencias_medio_minimo'] else 0
        reference_risk = CLASSES[2 if points >= 5 else 1 if points >= 2 else 0]
        check(points == row['puntos_riesgo'] == int(expected['puntos_riesgo_final'])
              and reference_risk == row['riesgo_referencia'] == expected['riesgo_referencia'], 'REFERENCE_RULE_MISMATCH')
    check(students['B1'] == students['B2'] and len(students['B1']) == 60, 'SOURCE_COHORT_MISMATCH')
    return {'audit_version': 'source-declarations-v1', 'input_sha256': SOURCE_HASH,
            'package_sha256': PACKAGE_HASH, 'source_events_verified': True, 'authenticity_verified': False,
            'students': 60, 'bimester_rows': 120, 'partial_grades': 720, 'attendance_windows': 120,
            'activity_windows': 120, 'derived_feature_matches': 360, 'reference_matches': 120,
            'latest_feature_availability': {term: value.isoformat() for term, value in latest.items()},
            'rounding_changes': rounding_changes, 'historical_predictions_preserved_in_source': len(old_predictions),
            'historical_alerts_preserved_in_source': len(old_alerts), 'workbook_modified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.source, args.package), ensure_ascii=False))
    except Exception:
        raise SystemExit('SOURCE_AUDIT_FAILED: sin publicar registros; revisar fechas, joins, escalas y hashes.') from None
