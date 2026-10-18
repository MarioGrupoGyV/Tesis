"""Conversor local del Excel real a los CSV del sistema (Bloque 4). NO importa nada al sistema.

    py -3.12 infra/convert_real_excel.py --excel <ruta al .xlsx> --out <carpeta FUERA de Git> [--identities]

Lee el libro (ruta por argumento, fuera del repositorio) con un lector propio de la biblioteca estándar (sin red, sin base de datos) y escribe
en `--out`: `cortes.csv` (contrato canónico de `csv_validation.py`), `cierres.csv` (formato de `load_closings.py`) y
`resumen_conversion.json` (solo conteos, códigos y SHA-256). Con `--identities` escribe además `identidades.local.csv` (código → nombre), el
único archivo con nombres, solo dentro de `--out`. No usa las hojas Alertas ni Intervenciones, no crea bitácoras y nunca escribe el riesgo del
Excel en las salidas (solo lo usa para verificar RIESGO_V1 en memoria). Misma entrada → mismos bytes.
"""
import argparse
import csv
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
from xml.etree import ElementTree
import zipfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.csv_validation import HEADERS as CORTES_HEADERS, parse_csv as parse_cortes  # noqa: E402
from app.services.risk_reference import ClosingInputs, InvalidClosingInputs, compute_riesgo_v1, mean_grade, validated  # noqa: E402
import load_closings  # noqa: E402

LIMA = ZoneInfo('America/Lima')
MAX_BYTES = 50 * 1024 * 1024
OUTPUTS = ('cortes.csv', 'cierres.csv')
IDENTITIES = 'identidades.local.csv'
SUMMARY = 'resumen_conversion.json'
SUSPICIOUS_COLUMN = re.compile(r'name|nombre|apellido|dni|correo|e-?mail|mail', re.I)
LEVELS = {'bajo': 'LOW', 'medio': 'MEDIUM', 'alto': 'HIGH'}
CAUSES = ('DUPLICATE_STUDENT_BIMESTER', 'CODE_OUTSIDE_COHORT', 'ATTENDED_EXCEEDS_SCHEDULED', 'GRADE_OUT_OF_SCALE',
          'DELIVERED_EXCEEDS_SCHEDULED', 'BIMESTER_MISSING')
CIERRES_HEADERS = load_closings.HEADERS

# Columnas que usa el conversor: (obligatorias, opcionales). Cualquier otra (incluidas las de nombre) se descarta al leer.
SHEETS = {
    'Estudiantes': (('codigo_estudiante', 'grado', 'seccion'), ()),
    'Bimestres': (('registro_id', 'codigo_estudiante', 'grado', 'seccion', 'bimestre', 'fecha_inicio', 'fecha_cierre', 'fecha_disponible',
                   'dias_programados', 'dias_asistidos', 'actividades_programadas', 'actividades_entregadas', 'participacion_1_5',
                   'numero_incidencias', 'promedio_0_20', 'fecha_corte_asistencia', 'fecha_disponible_asistencia', 'dias_programados_al_corte',
                   'dias_asistidos_al_corte', 'fecha_disponible_actividades', 'actividades_programadas_al_corte',
                   'actividades_entregadas_al_corte'), ('riesgo_referencia',)),
    'Calificaciones': (('registro_id', 'codigo_estudiante', 'bimestre', 'curso', 'nota_0_20', 'nota_parcial_0_20',
                        'fecha_disponible_parcial'), ()),
    'Incidencias': (('registro_id', 'codigo_estudiante', 'bimestre', 'fecha_incidencia'), ()),
    'Procesamiento': (('recepcion_id', 'codigo_original', 'bimestre_original', 'dias_programados_original', 'dias_asistidos_original',
                       'actividades_programadas_original', 'actividades_entregadas_original', 'nota_muestra_original'),
                      ('estado_validacion',)),
}


class ConversionError(Exception):
    """Código estable; nunca contiene valores del libro."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code, self.detail = code, detail


# ---------------------------------------------------------------- lector xlsx (solo biblioteca estándar)
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
BUILTIN_DATE_FORMATS = set(range(14, 23)) | {45, 46, 47}


def column_index(reference):
    letters = re.match(r'[A-Z]+', reference).group(0)
    index = 0
    for character in letters:
        index = index * 26 + ord(character) - 64
    return index - 1


def is_date_format(code):
    cleaned = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', '', code)
    return bool(re.search(r'[dmyhs]', cleaned, re.I))


class Workbook:
    def __init__(self, path):
        path = Path(path)
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ConversionError('EXCEL_UNAVAILABLE')
        try:
            self.archive = zipfile.ZipFile(path)
            workbook = ElementTree.fromstring(self.archive.read('xl/workbook.xml'))
            relations = ElementTree.fromstring(self.archive.read('xl/_rels/workbook.xml.rels'))
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError):
            raise ConversionError('EXCEL_UNREADABLE') from None
        targets = {item.get('Id'): item.get('Target') for item in relations.findall('rel:Relationship', NS)}
        self.sheets = {}
        for sheet in workbook.findall('m:sheets/m:sheet', NS):
            target = targets.get(sheet.get('{%s}id' % NS['r']), '')
            self.sheets[sheet.get('name')] = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        self.strings = self._strings()
        self.date_styles = self._date_styles()

    def _strings(self):
        if 'xl/sharedStrings.xml' not in self.archive.namelist():
            return []
        root = ElementTree.fromstring(self.archive.read('xl/sharedStrings.xml'))
        return [''.join(node.text or '' for node in item.iter('{%s}t' % NS['m'])) for item in root.findall('m:si', NS)]

    def _date_styles(self):
        if 'xl/styles.xml' not in self.archive.namelist():
            return set()
        root = ElementTree.fromstring(self.archive.read('xl/styles.xml'))
        custom = {int(item.get('numFmtId')): item.get('formatCode', '') for item in root.findall('m:numFmts/m:numFmt', NS)}
        styles = set()
        for index, xf in enumerate(root.findall('m:cellXfs/m:xf', NS)):
            number = int(xf.get('numFmtId', '0'))
            if number in BUILTIN_DATE_FORMATS or (number in custom and is_date_format(custom[number])):
                styles.add(index)
        return styles

    def rows(self, name):
        """Filas de la hoja como listas de valores (str, int, Decimal, date, bool o None)."""
        if name not in self.sheets:
            raise ConversionError('EXCEL_SHEET_MISSING', name)
        try:
            root = ElementTree.fromstring(self.archive.read(self.sheets[name]))
        except (KeyError, ElementTree.ParseError):
            raise ConversionError('EXCEL_UNREADABLE') from None
        result = []
        for row in root.findall('m:sheetData/m:row', NS):
            values = []
            for cell in row.findall('m:c', NS):
                position = column_index(cell.get('r')) if cell.get('r') else len(values)
                values.extend([None] * (position - len(values)))
                values.append(self._value(cell))
            result.append(values)
        return result

    def _value(self, cell):
        kind, raw = cell.get('t', 'n'), cell.find('m:v', NS)
        text = raw.text if raw is not None else None
        if kind == 'inlineStr':
            return ''.join(node.text or '' for node in cell.iter('{%s}t' % NS['m']))
        if text is None:
            return None
        if kind == 's':
            return self.strings[int(text)]
        if kind in ('str', 'e'):
            return text if kind == 'str' else None
        if kind == 'b':
            return text == '1'
        try:
            number = Decimal(text)
        except ArithmeticError:
            return None
        if int(cell.get('s', '0')) in self.date_styles:
            return date(1899, 12, 30) + timedelta(days=int(number))
        return int(number) if number == number.to_integral_value() else number


def read_table(book, name, required, optional=()):
    """Tabla de la hoja limitada a las columnas indicadas: el resto (nombres incluidos) nunca sale de esta función."""
    rows = book.rows(name)
    if not rows:
        raise ConversionError('EXCEL_COLUMN_MISSING', f'{name}:*')
    header = [str(item).strip() if item is not None else '' for item in rows[0]]
    for column in required:
        if column not in header:
            raise ConversionError('EXCEL_COLUMN_MISSING', f'{name}:{column}')
    wanted = [column for column in (*required, *optional) if column in header]
    positions = {column: header.index(column) for column in wanted}
    table = []
    for values in rows[1:]:
        if not any(item not in (None, '') for item in values):
            continue
        table.append({column: values[position] if position < len(values) else None for column, position in positions.items()})
    return table


def name_values(book):
    """Nombres del libro (solo en memoria) para la búsqueda automática de fugas: celdas de toda columna cuyo encabezado sea de nombre."""
    found = set()
    for name in book.sheets:
        try:
            rows = book.rows(name)
        except ConversionError:
            continue
        for header_index, header in enumerate(rows[0] if rows else []):
            if isinstance(header, str) and SUSPICIOUS_COLUMN.search(header) and 'nombre' in header.lower():
                found |= {str(row[header_index]).strip().casefold() for row in rows[1:]
                          if header_index < len(row) and isinstance(row[header_index], str) and len(row[header_index].strip()) >= 5}
    return found


# ---------------------------------------------------------------- conversión
def as_day(value, code='EXCEL_DATE_INVALID'):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value.strip()):
        return date.fromisoformat(value.strip())
    raise ConversionError(code)


def as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    return None


def as_number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    return None


def day_end(day):
    return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=LIMA).isoformat()


def percent(part, whole):
    """Porcentaje con enteros, mitad hacia arriba, dos decimales fijos."""
    hundredths = (part * 20000 + whole) // (2 * whole)
    return f'{hundredths // 100}.{hundredths % 100:02d}'


def classify_receptions(rows, cohort):
    """Las seis causas de rechazo de la hoja Procesamiento, recalculadas con los valores originales de cada recepción."""
    accepted, causes, agreement = {}, Counter(), Counter()
    for row in rows:
        code = str(row['codigo_original']).strip() if row['codigo_original'] is not None else ''
        bimester = str(row['bimestre_original']).strip() if row['bimestre_original'] is not None else ''
        scheduled, attended = as_int(row['dias_programados_original']), as_int(row['dias_asistidos_original'])
        planned, delivered = as_int(row['actividades_programadas_original']), as_int(row['actividades_entregadas_original'])
        grade = as_number(row['nota_muestra_original'])
        cause = None
        if not bimester:
            cause = 'BIMESTER_MISSING'
        elif code not in cohort:
            cause = 'CODE_OUTSIDE_COHORT'
        elif scheduled is not None and attended is not None and attended > scheduled:
            cause = 'ATTENDED_EXCEEDS_SCHEDULED'
        elif grade is not None and not Decimal(0) <= grade <= Decimal(20):
            cause = 'GRADE_OUT_OF_SCALE'
        elif planned is not None and delivered is not None and delivered > planned:
            cause = 'DELIVERED_EXCEEDS_SCHEDULED'
        elif (code, bimester) in accepted:
            cause = 'DUPLICATE_STUDENT_BIMESTER'
        if cause:
            causes[cause] += 1
        else:
            accepted[(code, bimester)] = True
        if 'estado_validacion' in row:
            sheet_rejected = str(row['estado_validacion']).strip().casefold() != 'valido'
            agreement['agree' if sheet_rejected == bool(cause) else 'disagree'] += 1
    return accepted, causes, agreement


def build(book, identities):
    cohort_rows = read_table(book, 'Estudiantes', *SHEETS['Estudiantes'])
    cohort = {str(row['codigo_estudiante']).strip(): (as_int(row['grado']), str(row['seccion']).strip()) for row in cohort_rows}
    receptions = read_table(book, 'Procesamiento', *SHEETS['Procesamiento'])
    academic = read_table(book, 'Bimestres', *SHEETS['Bimestres'])
    grades = read_table(book, 'Calificaciones', *SHEETS['Calificaciones'])
    incidents = read_table(book, 'Incidencias', *SHEETS['Incidencias'])
    counts = {'Estudiantes': len(cohort_rows), 'Procesamiento': len(receptions), 'Bimestres': len(academic),
              'Calificaciones': len(grades), 'Incidencias': len(incidents)}

    accepted, causes, agreement = classify_receptions(receptions, cohort)
    by_key = {}
    for row in academic:
        by_key.setdefault((str(row['codigo_estudiante']).strip(), str(row['bimestre']).strip()), row)
    course = {}
    for row in grades:
        course.setdefault((str(row['registro_id']).strip()), []).append(row)
    incident_days = {}
    for row in incidents:
        incident_days.setdefault(str(row['registro_id']).strip(), []).append(as_day(row['fecha_incidencia']))

    records, not_received = [], 0
    for key in sorted(accepted):
        row = by_key.get(key)
        if row is None:
            causes['NO_ACADEMIC_RECORD'] += 1
            continue
        record = prepare(row, key, cohort, course, incident_days)
        if isinstance(record, str):
            causes[record] += 1
        else:
            records.append(record)
    not_received = len(set(by_key) - set(accepted))

    # Corte por bimestre = disponibilidad de la última fuente de toda la cohorte aceptada (horizonte constante del protocolo).
    cutoffs = {}
    for record in records:
        cutoffs[record['bimester']] = max(cutoffs.get(record['bimester'], record['available_day']), record['available_day'])
    cortes, cierres = io.StringIO(), io.StringIO()
    cortes_writer = csv.writer(cortes, lineterminator='\n')
    cierres_writer = csv.writer(cierres, lineterminator='\n')
    cortes_writer.writerow(CORTES_HEADERS[:13])
    cierres_writer.writerow(CIERRES_HEADERS)
    ordered = sorted(records, key=lambda item: (item['code'], item['bimester']))
    for record in ordered:
        cortes_writer.writerow([record['code'], record['grade'], record['section'], day_end(cutoffs[record['bimester']]),
            record['close'].isoformat(), day_end(record['available_day']), record['start'].isoformat(), record['cut_grade'],
            record['cut_attendance'], record['cut_activities'], '', record['cut_incidents'], ''])
        cierres_writer.writerow([record['code'], record['bimester'], record['close'].isoformat(), day_end(record['closing_available']),
            record['close_grade'], record['days_scheduled'], record['days_attended'], record['activities_scheduled'],
            record['activities_delivered'], record['participation'], record['close_incidents']])
    identity_text = None
    if identities:
        names = read_names(book)
        identity_writer_buffer = io.StringIO()
        writer = csv.writer(identity_writer_buffer, lineterminator='\n')
        writer.writerow(('student_code', 'full_name'))
        for code in sorted(names):
            writer.writerow((code, names[code]))
        identity_text = identity_writer_buffer.getvalue()
    return SimpleNamespace(cortes=cortes.getvalue(), cierres=cierres.getvalue(), identities=identity_text, records=ordered, causes=causes,
                           agreement=agreement, counts=counts, cohort=cohort, cutoffs=cutoffs, not_received=not_received,
                           received=len(receptions), accepted_receptions=len(accepted))


def read_names(book):
    rows = book.rows('Estudiantes')
    header = [str(item).strip() if item is not None else '' for item in rows[0]]
    if 'codigo_estudiante' not in header or 'nombre_estudiante' not in header:
        raise ConversionError('EXCEL_COLUMN_MISSING', 'Estudiantes:nombre_estudiante')
    code_at, name_at = header.index('codigo_estudiante'), header.index('nombre_estudiante')
    return {str(row[code_at]).strip(): str(row[name_at]).strip() for row in rows[1:] if len(row) > max(code_at, name_at) and row[code_at]}


def prepare(row, key, cohort, course, incident_days):
    """Fila de cortes y de cierre de un estudiante-bimestre aceptado, o la causa de rechazo (str)."""
    code, bimester = key
    registro = str(row['registro_id']).strip()
    grade_level, section = as_int(row['grado']), str(row['seccion']).strip()
    if cohort.get(code) != (grade_level, section):
        return 'CODE_OUTSIDE_COHORT'
    closing = {name: as_int(row[name]) for name in ('dias_programados', 'dias_asistidos', 'actividades_programadas', 'actividades_entregadas',
                                                      'participacion_1_5', 'numero_incidencias', 'dias_programados_al_corte',
                                                      'dias_asistidos_al_corte', 'actividades_programadas_al_corte',
                                                      'actividades_entregadas_al_corte')}
    if any(value is None for value in closing.values()):
        return 'BIMESTER_MISSING'
    final_notes = [as_number(item['nota_0_20']) for item in course.get(registro, [])]
    partial_notes = [(as_number(item['nota_parcial_0_20']), item['fecha_disponible_parcial']) for item in course.get(registro, [])]
    if any(value is not None and not Decimal(0) <= value <= Decimal(20) for value in [*final_notes, *[n for n, _ in partial_notes]]):
        return 'GRADE_OUT_OF_SCALE'
    final_values = [value for value in final_notes if value is not None]
    close_grade = mean_grade(final_values) if final_values else as_number(row['promedio_0_20'])
    if close_grade is None:
        return 'GRADE_OUT_OF_SCALE'
    try:
        valid = validated(ClosingInputs(close_grade, closing['dias_programados'], closing['dias_asistidos'],
            closing['actividades_programadas'], closing['actividades_entregadas'], closing['participacion_1_5'], closing['numero_incidencias']))
    except InvalidClosingInputs as error:
        return {'GRADE_OUT_OF_SCALE': 'GRADE_OUT_OF_SCALE', 'ATTENDANCE_INCONSISTENT': 'ATTENDED_EXCEEDS_SCHEDULED',
                'ACTIVITIES_INCONSISTENT': 'DELIVERED_EXCEEDS_SCHEDULED'}.get(str(error), 'GRADE_OUT_OF_SCALE')
    if closing['dias_programados_al_corte'] <= 0 or closing['dias_asistidos_al_corte'] > closing['dias_programados_al_corte']:
        return 'ATTENDED_EXCEEDS_SCHEDULED'
    if closing['actividades_programadas_al_corte'] <= 0 or closing['actividades_entregadas_al_corte'] > closing['actividades_programadas_al_corte']:
        return 'DELIVERED_EXCEEDS_SCHEDULED'
    partial_values = [value for value, _ in partial_notes if value is not None]
    start, close, closing_available = as_day(row['fecha_inicio']), as_day(row['fecha_cierre']), as_day(row['fecha_disponible'])
    data_cut = as_day(row['fecha_corte_asistencia'])
    available = [as_day(row['fecha_disponible_asistencia']), as_day(row['fecha_disponible_actividades']),
                 *[as_day(day) for value, day in partial_notes if value is not None]]
    return {'code': code, 'bimester': bimester, 'grade': grade_level, 'section': section, 'start': start, 'close': close,
            'closing_available': closing_available, 'available_day': max(available),
            'cut_grade': str(mean_grade(partial_values)) if partial_values else '',
            'cut_attendance': percent(closing['dias_asistidos_al_corte'], closing['dias_programados_al_corte']),
            'cut_activities': percent(closing['actividades_entregadas_al_corte'], closing['actividades_programadas_al_corte']),
            'cut_incidents': sum(1 for day in incident_days.get(registro, []) if day <= data_cut),
            'close_grade': str(valid.average_grade), 'days_scheduled': closing['dias_programados'],
            'days_attended': closing['dias_asistidos'], 'activities_scheduled': closing['actividades_programadas'],
            'activities_delivered': closing['actividades_entregadas'], 'participation': closing['participacion_1_5'],
            'close_incidents': closing['numero_incidencias'], 'registro': registro,
            'sheet_incidents': len(incident_days.get(registro, [])),
            'sheet_level': LEVELS.get(str(row.get('riesgo_referencia') or '').strip().casefold())}


def verify(result):
    """Verificación local: RIESGO_V1 recalculado con el código del backend frente al riesgo del Excel (solo conteos y códigos)."""
    computed, mismatches, levels, incident_gap = {}, [], {}, []
    for record in result.records:
        inputs = ClosingInputs(Decimal(record['close_grade']), record['days_scheduled'], record['days_attended'], record['activities_scheduled'],
                               record['activities_delivered'], record['participation'], record['close_incidents'])
        level = compute_riesgo_v1(inputs).risk_level
        levels.setdefault(record['bimester'], Counter())[level] += 1
        computed[(record['code'], record['bimester'])] = level
        if record['sheet_level'] is not None and record['sheet_level'] != level:
            mismatches.append(f"{record['code']}:{record['bimester']}")
        if record['sheet_incidents'] != record['close_incidents']:
            incident_gap.append(f"{record['code']}:{record['bimester']}")
    with_reference = [record for record in result.records if record['sheet_level'] is not None]
    return {'reference_column_present': bool(with_reference), 'compared': len(with_reference),
            'matches': len(with_reference) - len(mismatches), 'mismatches': mismatches[:60],
            'recalculated_levels': {bimester: {name: counter.get(name, 0) for name in ('LOW', 'MEDIUM', 'HIGH')}
                                    for bimester, counter in sorted(levels.items())},
            'incident_count_differs_from_sheet': incident_gap[:60]}


def check_outputs(result):
    """El CSV de cortes se acepta con el validador del backend y los cierres con el de `load_closings`."""
    period = SimpleNamespace(start_date=date(min(item['start'] for item in result.records).year, 1, 1),
                             end_date=date(max(item['close'] for item in result.records).year, 12, 31))
    parsed = parse_cortes(result.cortes.encode('utf-8'), period, {'participation': (1, 5), 'grade': (0, 20)})
    if parsed.errors or len(parsed.rows) != len(result.records):
        raise ConversionError('CORTES_CSV_REJECTED', f'{len(parsed.errors)} errores')
    with tempfile.TemporaryDirectory() as folder:       # copia efímera en la carpeta temporal del sistema, fuera del repositorio
        path = Path(folder) / 'cierres.csv'
        path.write_bytes(result.cierres.encode('utf-8'))
        try:
            rows = load_closings.parse_csv(path)
        except load_closings.ClosingCsvError as error:
            raise ConversionError('CIERRES_CSV_REJECTED', str(error).split(':')[0]) from None
    if len(rows) != len(result.records):
        raise ConversionError('CIERRES_CSV_REJECTED', 'filas')
    horizons = {}
    for record in result.records:
        horizons.setdefault(record['bimester'], set()).add((record['close'] - result.cutoffs[record['bimester']]).days)
    return {'cortes_rows': len(parsed.rows), 'cierres_rows': len(rows),
            'horizon_days': {bimester: sorted(days) for bimester, days in sorted(horizons.items())}}


def name_check(files, names):
    """Búsqueda en memoria: ninguna salida (salvo identidades) contiene un nombre del libro ni columnas sospechosas."""
    leaks, columns = 0, []
    for filename, content in files.items():
        folded = content.casefold()
        leaks += sum(1 for item in names if item in folded)
        if filename.endswith('.csv'):
            header = next(csv.reader(io.StringIO(content)), [])
            columns += [f'{filename}:{item}' for item in header if SUSPICIOUS_COLUMN.search(item)]
    return {'files_checked': len(files), 'name_matches': leaks, 'suspicious_columns': columns}


def inside_git_tree(path):
    resolved = Path(path).resolve()
    return any((candidate / '.git').exists() for candidate in (resolved, *resolved.parents))


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def convert(excel, out, identities=False):
    if inside_git_tree(out):
        raise ConversionError('OUTPUT_INSIDE_GIT')
    if inside_git_tree(Path(excel).parent):
        raise ConversionError('EXCEL_INSIDE_GIT')
    out = Path(out)
    if out.exists() and not out.is_dir():
        raise ConversionError('OUTPUT_NOT_A_DIRECTORY')
    book = Workbook(excel)
    result = build(book, identities)
    if not result.records:
        raise ConversionError('NO_VALID_ROWS')
    structure = check_outputs(result)
    names = name_values(book)
    files = {'cortes.csv': result.cortes, 'cierres.csv': result.cierres}
    summary = {
        'tool': 'convert_real_excel', 'sheets_rows': result.counts, 'received': result.received,
        'accepted': len(result.records), 'rejected': sum(result.causes.values()),
        'rejected_by_cause': {cause: result.causes.get(cause, 0) for cause in CAUSES} | (
            {'NO_ACADEMIC_RECORD': result.causes['NO_ACADEMIC_RECORD']} if result.causes.get('NO_ACADEMIC_RECORD') else {}),
        'academic_rows_without_valid_reception': result.not_received,
        'agreement_with_sheet_status': {'agree': result.agreement.get('agree', 0), 'disagree': result.agreement.get('disagree', 0)},
        'cortes': {'rows': len(result.records), 'students': len({item['code'] for item in result.records}),
                   'bimesters': sorted({item['bimester'] for item in result.records}),
                   'cutoff_by_bimester': {bimester: day.isoformat() for bimester, day in sorted(result.cutoffs.items())},
                   'participation_blank': all(line.split(',')[10] == '' for line in result.cortes.splitlines()[1:]),
                   'risk_column_written': False},
        'structure_check': structure, 'verification': verify(result),
        'name_check': name_check(files, names),
        'outputs': {name: {'rows': len(content.splitlines()) - 1, 'sha256': sha256(content)} for name, content in files.items()},
    }
    if result.identities is not None:
        summary['identities'] = {'file': IDENTITIES, 'rows': len(result.identities.splitlines()) - 1}
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (out / name).write_bytes(content.encode('utf-8'))
    if result.identities is not None:
        (out / IDENTITIES).write_bytes(result.identities.encode('utf-8'))
    text = json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
    (out / SUMMARY).write_bytes(text.encode('utf-8'))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--excel', type=Path, required=True, help='Libro .xlsx (fuera del repositorio)')
    parser.add_argument('--out', type=Path, required=True, help='Carpeta de salida FUERA de Git')
    parser.add_argument('--identities', action='store_true', help='Escribe además identidades.local.csv (código → nombre) solo en --out')
    args = parser.parse_args(argv)
    try:
        summary = convert(args.excel, args.out, args.identities)
    except ConversionError as error:
        print(json.dumps({'code': error.code, **({'detail': error.detail} if error.detail else {})}, ensure_ascii=True))
        return 2
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
