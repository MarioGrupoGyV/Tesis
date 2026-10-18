"""CLI de cierres: validación del CSV local (sin docker ni red)."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import load_closings as cli  # noqa: E402

HEADER = ','.join(cli.HEADERS)
GOOD = 'E001,B1,2026-05-08,2026-05-11T12:00:00-05:00,13.95,45,43,24,22,5,0'


class ParseClosingCsv(unittest.TestCase):
    def parse(self, *lines, encoding='utf-8'):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cierres.csv'
            path.write_text('\n'.join(lines) + '\n', encoding=encoding)
            return cli.parse_csv(path)

    def test_valid_rows_are_typed(self):
        rows = self.parse(HEADER, GOOD)
        self.assertEqual(rows, [{'student_code': 'E001', 'bimester': 'B1', 'closing_date': '2026-05-08',
            'closing_available_at': '2026-05-11T12:00:00-05:00', 'average_grade': '13.95', 'days_scheduled': 45,
            'days_attended': 43, 'activities_scheduled': 24, 'activities_delivered': 22, 'participation_level': 5,
            'behavior_incidents': 0, 'line': 2}])

    def test_any_extra_or_missing_column_rejects_the_file_including_names_and_risk(self):
        for header in (HEADER + ',nombre_estudiante', HEADER + ',riesgo_referencia', HEADER.replace('student_code', 'nombre'),
                       HEADER.rsplit(',', 1)[0]):
            with self.subTest(header=header), self.assertRaisesRegex(cli.ClosingCsvError, '^CLOSING_CSV_HEADERS_INVALID$'):
                self.parse(header, GOOD)

    def test_invalid_rows_report_only_line_numbers(self):
        bad = ['E002,B1,2026-13-40,2026-05-11T12:00:00-05:00,13.95,45,43,24,22,5,0',        # fecha imposible
               'E003,B1,2026-05-08,2026-05-11T12:00:00,13.95,45,43,24,22,5,0',               # sin zona horaria
               'E004,B1,2026-05-08,2026-05-11T12:00:00-05:00,13,95,45,43,24,22,5,0',         # coma decimal → columnas de más
               'Álvaro Pérez,B1,2026-05-08,2026-05-11T12:00:00-05:00,13.95,45,43,24,22,5,0',  # un nombre no es un código
               'E006,B1,2026-05-08,2026-05-11T12:00:00-05:00,13.955,45,43,24,22,5,0']        # tres decimales
        with self.assertRaises(cli.ClosingCsvError) as error:
            self.parse(HEADER, GOOD, *bad)
        self.assertEqual(str(error.exception), 'CLOSING_CSV_ROWS_INVALID:3,4,5,6,7')
        self.assertNotIn('lvaro', str(error.exception))

    def test_empty_and_missing_files(self):
        with self.assertRaisesRegex(cli.ClosingCsvError, '^CLOSING_CSV_EMPTY$'):
            self.parse(HEADER)
        with self.assertRaisesRegex(cli.ClosingCsvError, '^CLOSING_CSV_UNAVAILABLE$'):
            cli.parse_csv(Path('no-existe.csv'))

    def test_active_target_is_refused(self):
        self.assertIn('ACTIVE_TARGET_FORBIDDEN', Path(cli.__file__).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
