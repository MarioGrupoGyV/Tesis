"""Bloque 4: conversor local del Excel real. Solo libros FICTICIOS generados aquí (códigos `T-0001`, semilla fija); nunca se guardan en el repo.

El libro ficticio imita las hojas y columnas que usa el conversor, incluidas las columnas de nombre (inventadas) y las hojas Alertas/Intervenciones,
para comprobar que ningún nombre ni el riesgo del libro llegan a las salidas.
"""
import ast
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import random
import socket
import sys
import zipfile
from xml.sax.saxutils import escape

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
import convert_real_excel as converter  # noqa: E402
from app.services.risk_reference import ClosingInputs, compute_riesgo_v1  # noqa: E402

CALENDAR = {'B1': dict(start=date(2026, 3, 9), close=date(2026, 5, 8), closing_available=date(2026, 5, 11), cut=date(2026, 4, 17),
                       available=date(2026, 4, 21)),
            'B2': dict(start=date(2026, 5, 18), close=date(2026, 7, 17), closing_available=date(2026, 7, 20), cut=date(2026, 6, 26),
                       available=date(2026, 6, 30))}
COURSES = ('Curso 1', 'Curso 2', 'Curso 3', 'Curso 4', 'Curso 5', 'Curso 6')
NAME_WORDS = ('Zzquux', 'Qwertyx', 'Plokijh', 'Mnbvcxz')
LEVEL_NAME = {'LOW': 'Bajo', 'MEDIUM': 'Medio', 'HIGH': 'Alto'}


# ------------------------------------------------------------------ escritor mínimo de .xlsx (solo biblioteca estándar)
def column_letter(index):
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def cell_xml(position, value):
    if value is None:
        return ''
    if isinstance(value, date):
        return f'<c r="{position}" s="1"><v>{(value - date(1899, 12, 30)).days}</v></c>'
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return f'<c r="{position}"><v>{value}</v></c>'
    return f'<c r="{position}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def write_book(path, sheets):
    parts = {
        '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        '_rels/.rels': '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/styles.xml': '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>',
    }
    sheet_tags, relations = [], []
    for number, (name, rows) in enumerate(sheets.items(), start=1):
        body = ''.join('<row r="%d">%s</row>' % (r, ''.join(cell_xml(f'{column_letter(c)}{r}', v) for c, v in enumerate(row)))
                       for r, row in enumerate(rows, start=1))
        parts[f'xl/worksheets/sheet{number}.xml'] = ('<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                                                     f'<sheetData>{body}</sheetData></worksheet>')
        sheet_tags.append(f'<sheet name="{escape(name)}" sheetId="{number}" r:id="rId{number}"/>')
        relations.append(f'<Relationship Id="rId{number}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{number}.xml"/>')
    parts['xl/workbook.xml'] = ('<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                                f'<sheets>{"".join(sheet_tags)}</sheets></workbook>')
    relations.append('<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    parts['xl/_rels/workbook.xml.rels'] = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                           f'{"".join(relations)}</Relationships>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return Path(path)


# ------------------------------------------------------------------ libro ficticio
def fictitious_sheets(anomalies=(), seed=60112026, drop_sheet=None, drop_column=None, risk_wrong=None, final_note_override=None):
    rng = random.Random(seed)
    codes = [f'T-{index:04d}' for index in range(1, 61)]
    names = {code: f'{NAME_WORDS[i % 4]} {NAME_WORDS[(i + 1) % 4]} {code[2:]}' for i, code in enumerate(codes)}
    section = {code: 'A' if i < 30 else 'B' for i, code in enumerate(codes)}
    students = [['codigo_estudiante', 'nombre_estudiante', 'grado', 'seccion']] + [[c, names[c], 3, section[c]] for c in codes]
    bim_header = ['registro_id', 'codigo_estudiante', 'grado', 'seccion', 'bimestre', 'fecha_inicio', 'fecha_cierre', 'fecha_disponible',
                  'dias_programados', 'dias_asistidos', 'actividades_programadas', 'actividades_entregadas', 'participacion_1_5',
                  'numero_incidencias', 'promedio_0_20', 'riesgo_referencia', 'nombre_estudiante', 'fecha_corte_asistencia',
                  'fecha_disponible_asistencia', 'dias_programados_al_corte', 'dias_asistidos_al_corte', 'fecha_disponible_actividades',
                  'actividades_programadas_al_corte', 'actividades_entregadas_al_corte']
    grade_header = ['calificacion_id', 'registro_id', 'codigo_estudiante', 'bimestre', 'curso', 'nota_0_20', 'nombre_estudiante',
                    'nota_parcial_0_20', 'fecha_disponible_parcial']
    incident_header = ['incidencia_id', 'registro_id', 'codigo_estudiante', 'bimestre', 'fecha_incidencia', 'nombre_estudiante']
    reception_header = ['recepcion_id', 'lote_bimestre', 'codigo_original', 'bimestre_original', 'dias_programados_original',
                        'dias_asistidos_original', 'actividades_programadas_original', 'actividades_entregadas_original',
                        'participacion_original', 'nota_muestra_original', 'estado_validacion', 'motivo_validacion', 'registro_aceptado_id',
                        'nombre_estudiante']
    academic, grades, incidents, receptions, closing_values = [bim_header], [grade_header], [incident_header], [reception_header], {}
    for code in codes:
        latent = rng.random()
        for bimester, calendar in CALENDAR.items():
            registro = f'{code}_{bimester}'
            scheduled, planned = 45, 24
            attended = min(scheduled, max(0, round(scheduled * (1 - 0.5 * latent) + rng.randint(-2, 2))))
            delivered = min(planned, max(0, round(planned * (1 - 0.6 * latent) + rng.randint(-2, 2))))
            participation = max(1, min(5, 5 - round(4 * latent) + rng.randint(-1, 0)))
            counted = rng.randint(0, 5)
            final_notes = [Decimal(f'{max(0, min(20, 19 - 11 * latent + rng.uniform(-2, 2))):.2f}') for _ in COURSES]
            if final_note_override and final_note_override[0] == registro:
                final_notes[0] = Decimal(final_note_override[1])
            partials = [Decimal(f'{max(0, min(20, float(note) + rng.uniform(-1, 1))):.2f}') for note in final_notes]
            average = converter.mean_grade(final_notes)
            level = compute_riesgo_v1(ClosingInputs(average, scheduled, attended, planned, delivered, participation, counted)).risk_level
            closing_values[registro] = (code, bimester, scheduled, attended, planned, delivered, participation, final_notes[0])
            shown_level = LEVEL_NAME[level] if risk_wrong != registro else LEVEL_NAME['HIGH' if level != 'HIGH' else 'LOW']
            academic.append([registro, code, 3, section[code], bimester, calendar['start'], calendar['close'], calendar['closing_available'],
                             scheduled, attended, planned, delivered, participation, counted, average, shown_level, names[code], calendar['cut'],
                             calendar['available'] - timedelta(days=1), 30, min(30, round(30 * (1 - 0.4 * latent))),
                             calendar['available'], 16, min(16, round(16 * (1 - 0.5 * latent)))])
            for number, (course, note, partial) in enumerate(zip(COURSES, final_notes, partials)):
                grades.append([f'CAL-{registro}-{number}', registro, code, bimester, course, note, names[code], partial,
                               calendar['cut'] - timedelta(days=rng.randint(3, 8))])
            for number in range(counted):
                incidents.append([f'INC-{registro}-{number}', registro, code, bimester,
                                  calendar['start'] + timedelta(days=rng.randint(0, 59)), names[code]])
            receptions.append([f'PRO-{registro}', bimester, code, bimester, scheduled, attended, planned, delivered, participation,
                               final_notes[0], 'Valido', 'Validación de clave y rangos', registro, names[code]])

    def bad(cause):
        code, bimester, scheduled, attended, planned, delivered, participation, note = closing_values['T-0003_B1']
        row = ['PRO-BAD-' + cause, bimester, code, bimester, scheduled, attended, planned, delivered, participation, note,
               'Rechazado', cause, None, names[code]]
        if cause == 'DUPLICATE_STUDENT_BIMESTER':
            return row
        if cause == 'CODE_OUTSIDE_COHORT':
            row[2] = 'T-9999'
        elif cause == 'ATTENDED_EXCEEDS_SCHEDULED':
            row[5] = scheduled + 3
        elif cause == 'GRADE_OUT_OF_SCALE':
            row[9] = Decimal('25')
        elif cause == 'DELIVERED_EXCEEDS_SCHEDULED':
            row[7] = planned + 2
        elif cause == 'BIMESTER_MISSING':
            row[3] = None
        return row
    for cause in anomalies:
        receptions.append(bad(cause))
    sheets = {'Resumen': [[None], ['Registro ficticio']], 'Estudiantes': students, 'Bimestres': academic, 'Calificaciones': grades,
              'Incidencias': incidents, 'Procesamiento': receptions,
              'Alertas': [['alerta_id', 'codigo_estudiante', 'nombre_estudiante'], ['ALE0001', codes[0], names[codes[0]]]],
              'Intervenciones': [['intervencion_id', 'alerta_id'], ['INT0001', 'ALE0001']]}
    if drop_sheet:
        sheets.pop(drop_sheet)
    if drop_column:
        sheet, column = drop_column
        header = sheets[sheet][0]
        index = header.index(column)
        sheets[sheet] = [[value for position, value in enumerate(row) if position != index] for row in sheets[sheet]]
    return sheets, names


@pytest.fixture
def book(tmp_path):
    sheets, names = fictitious_sheets(anomalies=converter.CAUSES)
    return write_book(tmp_path / 'ficticio.xlsx', sheets), names


def read(path):
    return Path(path).read_bytes()


def run(book_path, out):
    return converter.convert(book_path, out)


# ------------------------------------------------------------------ pruebas
def test_produces_exactly_120_valid_rows_and_one_rejection_per_cause(book, tmp_path):
    path, _ = book
    summary = run(path, tmp_path / 'out')
    assert summary['received'] == 126 and summary['accepted'] == 120 and summary['rejected'] == 6
    assert summary['rejected_by_cause'] == {cause: 1 for cause in converter.CAUSES}
    assert summary['cortes'] == {**summary['cortes'], 'rows': 120, 'students': 60, 'bimesters': ['B1', 'B2'],
                                 'participation_blank': True, 'risk_column_written': False}
    assert summary['agreement_with_sheet_status'] == {'agree': 126, 'disagree': 0}
    lines = read(tmp_path / 'out' / 'cortes.csv').decode().splitlines()
    assert len(lines) == 121 and lines[0] == ','.join(converter.CORTES_HEADERS[:13])
    assert set(summary['structure_check']['horizon_days']['B1']) == {17} and set(summary['structure_check']['horizon_days']['B2']) == {17}
    assert summary['cortes']['cutoff_by_bimester'] == {'B1': '2026-04-21', 'B2': '2026-06-30'}
    assert summary['sheets_rows']['Procesamiento'] == 126 and 'Alertas' not in summary['sheets_rows'] and 'Intervenciones' not in summary['sheets_rows']


@pytest.mark.parametrize('cause', converter.CAUSES)
def test_each_rejection_cause_is_detected_alone(cause, tmp_path):
    sheets, _ = fictitious_sheets(anomalies=[cause])
    summary = run(write_book(tmp_path / 'uno.xlsx', sheets), tmp_path / 'out')
    assert summary['received'] == 121 and summary['accepted'] == 120 and summary['rejected'] == 1
    assert summary['rejected_by_cause'][cause] == 1 and sum(summary['rejected_by_cause'].values()) == 1


def test_bad_values_in_the_academic_sheet_are_rejected_with_the_same_causes(tmp_path):
    sheets, _ = fictitious_sheets(final_note_override=('T-0005_B2', '25'))
    summary = run(write_book(tmp_path / 'nota.xlsx', sheets), tmp_path / 'out')
    assert summary['accepted'] == 119 and summary['rejected_by_cause']['GRADE_OUT_OF_SCALE'] == 1
    assert 'T-0005,B2' not in read(tmp_path / 'out' / 'cierres.csv').decode()


def test_destination_inside_git_is_rejected_and_nothing_is_written(book, tmp_path):
    path, _ = book
    repository = tmp_path / 'repo'
    (repository / '.git').mkdir(parents=True)
    with pytest.raises(converter.ConversionError) as error:
        run(path, repository / 'salida')
    assert error.value.code == 'OUTPUT_INSIDE_GIT' and not (repository / 'salida').exists()
    assert converter.main(['--excel', str(path), '--out', str(repository / 'otra')]) == 2
    with pytest.raises(converter.ConversionError) as error:                       # el libro tampoco puede estar dentro de Git
        run(write_book(repository / 'dentro.xlsx', fictitious_sheets()[0]), tmp_path / 'fuera')
    assert error.value.code == 'EXCEL_INSIDE_GIT'


def test_same_input_gives_identical_bytes_and_summary_matches_files(book, tmp_path):
    path, _ = book
    first, second = run(path, tmp_path / 'a'), run(path, tmp_path / 'b')
    for name in ('cortes.csv', 'cierres.csv', 'resumen_conversion.json'):
        assert read(tmp_path / 'a' / name) == read(tmp_path / 'b' / name)
    for name in ('cortes.csv', 'cierres.csv'):
        assert first['outputs'][name]['sha256'] == hashlib.sha256(read(tmp_path / 'a' / name)).hexdigest() == second['outputs'][name]['sha256']
    raw = read(tmp_path / 'a' / 'cortes.csv')
    assert b'\r' not in raw and not raw.startswith(b'\xef\xbb\xbf')


def test_outputs_pass_the_backend_validators_and_have_no_risk(book, tmp_path):
    path, _ = book
    run(path, tmp_path / 'out')
    from app.services.csv_validation import parse_csv
    parsed = parse_csv(read(tmp_path / 'out' / 'cortes.csv'), type('Period', (), {'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31)}))
    assert parsed.errors == [] and len(parsed.rows) == 120
    assert all(row['participation_level'] is None and row['age_years'] is None for row in parsed.rows)
    rows = converter.load_closings.parse_csv(tmp_path / 'out' / 'cierres.csv')
    assert len(rows) == 120 and list(rows[0])[:-1] == list(converter.CIERRES_HEADERS)
    first_line = read(tmp_path / 'out' / 'cierres.csv').decode().splitlines()[0]
    assert first_line == ','.join(converter.load_closings.HEADERS)
    for name in ('cortes.csv', 'cierres.csv', 'resumen_conversion.json'):
        text = read(tmp_path / 'out' / name).decode()
        assert 'riesgo' not in text.lower().split('\n')[0] and not any(level in text for level in ('Bajo', 'Medio', 'Alto'))


def test_no_names_in_outputs_even_if_the_workbook_has_them_and_identities_only_on_request(book, tmp_path):
    path, names = book
    summary = run(path, tmp_path / 'out')
    assert summary['name_check'] == {'files_checked': 2, 'name_matches': 0, 'suspicious_columns': []}
    assert 'identities' not in summary and not (tmp_path / 'out' / 'identidades.local.csv').exists()
    for name in ('cortes.csv', 'cierres.csv', 'resumen_conversion.json'):
        text = read(tmp_path / 'out' / name).decode()
        assert not any(word in text for word in NAME_WORDS)
    with_identities = converter.convert(path, tmp_path / 'con', identities=True)
    assert with_identities['identities'] == {'file': 'identidades.local.csv', 'rows': 60}
    identities = read(tmp_path / 'con' / 'identidades.local.csv').decode().splitlines()
    assert identities[0] == 'student_code,full_name' and len(identities) == 61 and names['T-0001'] in identities[1]
    for name in ('cortes.csv', 'cierres.csv', 'resumen_conversion.json'):
        assert not any(word in read(tmp_path / 'con' / name).decode() for word in NAME_WORDS)
    assert read(tmp_path / 'con' / 'cortes.csv') == read(tmp_path / 'out' / 'cortes.csv')
    assert sorted(item.name for item in (tmp_path / 'con').iterdir()) == ['cierres.csv', 'cortes.csv', 'identidades.local.csv', 'resumen_conversion.json']


def test_missing_sheet_or_column_fails_with_stable_code_and_no_values(tmp_path, capsys):
    sheets, names = fictitious_sheets(drop_sheet='Incidencias')
    assert converter.main(['--excel', str(write_book(tmp_path / 'a.xlsx', sheets)), '--out', str(tmp_path / 'o1')]) == 2
    output = capsys.readouterr().out
    assert json.loads(output)['code'] == 'EXCEL_SHEET_MISSING' and not any(word in output for word in NAME_WORDS)
    sheets, _ = fictitious_sheets(drop_column=('Bimestres', 'dias_asistidos'))
    assert converter.main(['--excel', str(write_book(tmp_path / 'b.xlsx', sheets)), '--out', str(tmp_path / 'o2')]) == 2
    failure = json.loads(capsys.readouterr().out)
    assert failure == {'code': 'EXCEL_COLUMN_MISSING', 'detail': 'Bimestres:dias_asistidos'}
    assert not (tmp_path / 'o1').exists() and not (tmp_path / 'o2').exists()
    (tmp_path / 'roto.xlsx').write_bytes(b'no es un libro')
    assert converter.main(['--excel', str(tmp_path / 'roto.xlsx'), '--out', str(tmp_path / 'o3')]) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'EXCEL_UNREADABLE'


def test_local_verification_recalculates_risk_and_reports_differences_only_by_code(tmp_path):
    sheets, _ = fictitious_sheets(risk_wrong='T-0007_B2')
    summary = run(write_book(tmp_path / 'riesgo.xlsx', sheets), tmp_path / 'out')
    verification = summary['verification']
    assert verification['reference_column_present'] and verification['compared'] == 120
    assert verification['matches'] == 119 and verification['mismatches'] == ['T-0007:B2']
    assert sum(verification['recalculated_levels']['B1'].values()) == 60
    clean = run(write_book(tmp_path / 'ok.xlsx', fictitious_sheets()[0]), tmp_path / 'ok')
    assert clean['verification']['matches'] == 120 and clean['verification']['mismatches'] == []


def test_percentages_and_means_use_half_up_with_integers():
    assert converter.percent(29, 30) == '96.67' and converter.percent(1, 8) == '12.50' and converter.percent(1, 3) == '33.33'
    assert converter.percent(2, 3) == '66.67' and converter.percent(0, 30) == '0.00' and converter.percent(30, 30) == '100.00'
    assert converter.percent(1, 16) == '6.25' and converter.percent(1, 160) == '0.63'            # 0,625 → 0,63 (mitad hacia arriba)
    assert str(converter.mean_grade([Decimal('10.99'), Decimal('11.00')])) == '11.00'


def test_incidents_are_counted_up_to_the_cut_and_dates_use_lima(book, tmp_path):
    path, _ = book
    run(path, tmp_path / 'out')
    line = read(tmp_path / 'out' / 'cortes.csv').decode().splitlines()[1].split(',')
    assert line[3] == '2026-04-21T23:59:59-05:00' and line[4] == '2026-05-08' and line[6] == '2026-03-09'
    assert line[5].endswith('T23:59:59-05:00') and line[10] == '' and line[12] == ''


def test_module_has_no_network_or_database_imports_and_runs_with_sockets_disabled(book, tmp_path, monkeypatch):
    tree = ast.parse(Path(converter.__file__).read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split('.')[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split('.')[0])
    assert not imported & {'requests', 'httpx', 'sqlalchemy', 'socket', 'urllib', 'http', 'psycopg', 'aiohttp'}

    def forbidden(*args, **kwargs):
        raise AssertionError('el conversor no debe abrir conexiones')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    path, _ = book
    assert run(path, tmp_path / 'sin-red')['accepted'] == 120
