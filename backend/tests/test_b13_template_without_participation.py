"""Bloque 9 (cierre): plantilla de importación sin participación. Datos ficticios.

La plantilla vigente tiene 12 columnas. Un archivo antiguo de 13 columnas se sigue aceptando; en un periodo REAL la participación se ignora y
no se guarda (la huella de la fila es la misma que sin la columna). El formato del generador sintético no cambia.
"""
from datetime import date
from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.services.csv_validation import HEADERS, TEMPLATE_HEADERS, parse_csv

REAL = SimpleNamespace(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), data_origin='REAL')
SYNTHETIC = SimpleNamespace(start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), data_origin='SYNTHETIC')
VALUES = {'student_code': 'T-0001', 'grade': '3', 'section': 'A', 'cutoff_at': '2026-04-21T23:59:59-05:00', 'target_date': '2026-05-08',
          'available_at': '2026-04-21T23:59:59-05:00', 'window_start': '2026-03-09', 'average_grade': '12.50', 'attendance_pct': '88.00',
          'activities_pct': '70.00', 'participation_level': '3', 'behavior_incidents': '1', 'age_years': ''}


def csv(headers, values=VALUES):
    return (','.join(headers) + '\n' + ','.join(values.get(h, '') for h in headers) + '\n').encode()


def test_template_has_twelve_columns_without_participation():
    assert len(TEMPLATE_HEADERS) == 12 and 'participation_level' not in TEMPLATE_HEADERS
    assert list(TEMPLATE_HEADERS) == [h for h in HEADERS if h != 'participation_level']


def test_file_without_the_column_is_accepted():
    parsed = parse_csv(csv(TEMPLATE_HEADERS), REAL, {'participation': (1, 5)})
    assert parsed.errors == [] and len(parsed.rows) == 1 and parsed.rows[0]['participation_level'] is None
    assert parsed.rows[0]['average_grade'] is not None and parsed.rows[0]['behavior_incidents'] == 1


def test_old_file_with_the_column_is_accepted_and_participation_ignored_in_real():
    old = parse_csv(csv(HEADERS), REAL, {'participation': (1, 5)})
    new = parse_csv(csv(TEMPLATE_HEADERS), REAL, {'participation': (1, 5)})
    assert old.errors == [] and old.rows[0]['participation_level'] is None              # no se lee ni se guarda
    assert old.rows[0]['row_sha256'] == new.rows[0]['row_sha256']                       # misma fila que sin la columna
    out_of_scale = parse_csv(csv(HEADERS, {**VALUES, 'participation_level': '9'}), REAL, {'participation': (1, 5)})
    assert out_of_scale.errors == [] and out_of_scale.rows[0]['participation_level'] is None   # ni siquiera se valida


def test_synthetic_generator_format_is_unchanged():
    parsed = parse_csv(csv(HEADERS), SYNTHETIC, {'participation': (1, 5)})
    assert parsed.errors == [] and parsed.rows[0]['participation_level'] == 3


def test_any_other_header_set_is_still_rejected():
    with pytest.raises(AppError) as error:
        parse_csv(csv(TEMPLATE_HEADERS[:-1]), REAL)
    assert error.value.code == 'CSV_HEADERS'
