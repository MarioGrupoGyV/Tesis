"""CLI interna: carga insumos de cierre desde un CSV de códigos a un destino aislado; el backend aplica la regla del periodo
(RIESGO_V2 en los protocolos nuevos, ADR 013: la participación puede venir vacía y no se usa).

Solo códigos y números: el CSV con cualquier otra columna (p. ej. nombres) se rechaza completo. El backend calcula
componentes y nivel; el CSV no puede traer el riesgo. Todo o nada. No actúa sobre el destino ACTIVE.

    py -3.12 infra/load_closings.py --target <destino.json> --period-id <uuid> --actor-email <correo> --csv <cierres.csv>
"""
import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

HEADERS = ('student_code', 'bimester', 'closing_date', 'closing_available_at', 'average_grade', 'days_scheduled',
           'days_attended', 'activities_scheduled', 'activities_delivered', 'participation_level', 'behavior_incidents')
INTEGERS = ('days_scheduled', 'days_attended', 'activities_scheduled', 'activities_delivered',
            'participation_level', 'behavior_incidents')
MAX_ROWS = 2000


class ClosingCsvError(ValueError):
    """Código estable sin valores del archivo."""


def parse_csv(path: Path) -> list[dict]:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ClosingCsvError('CLOSING_CSV_UNAVAILABLE')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != HEADERS:
            raise ClosingCsvError('CLOSING_CSV_HEADERS_INVALID')
        rows, errors = [], []
        for line, values in enumerate(reader, start=2):
            if len(rows) + len(errors) >= MAX_ROWS:
                raise ClosingCsvError('CLOSING_CSV_TOO_MANY_ROWS')
            if len(values) != len(HEADERS):
                errors.append(line)
                continue
            item = dict(zip(HEADERS, values))
            try:
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,39}', item['student_code']):
                    raise ValueError
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,20}', item['bimester']):
                    raise ValueError
                date.fromisoformat(item['closing_date'])
                if datetime.fromisoformat(item['closing_available_at']).tzinfo is None:
                    raise ValueError
                if not re.fullmatch(r'[0-9]{1,2}(?:\.[0-9]{1,2})?', item['average_grade']):
                    raise ValueError
                Decimal(item['average_grade'])
                for key in INTEGERS:
                    if key == 'participation_level' and item[key] == '':
                        item[key] = None            # RIESGO_V2 no la usa; V1 la rechaza en el backend si falta
                        continue
                    if not re.fullmatch(r'[0-9]{1,6}', item[key]):
                        raise ValueError
                    item[key] = int(item[key])
            except (ValueError, InvalidOperation):
                errors.append(line)
                continue
            rows.append({**item, 'line': line})
    if errors:
        raise ClosingCsvError('CLOSING_CSV_ROWS_INVALID:' + ','.join(str(line) for line in errors[:20]))
    if not rows:
        raise ClosingCsvError('CLOSING_CSV_EMPTY')
    return rows


CODE = r'''
import json, sys
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import select
from app.core.config import Settings
from app.core.database import Database
from app.core.errors import AppError
from app.models.s1 import AppUser
from app.services.risk_reference import ClosingInputs
from app.services.risk_reference_store import ClosingRow, load_closings
p = json.load(sys.stdin)
db = Database(Settings())
with db.session_factory() as s:
    actor = s.scalar(select(AppUser).where(AppUser.email == p['actor_email'], AppUser.role == 'ADMIN', AppUser.is_active))
    if actor is None:
        print(json.dumps({'code': 'ACTOR_NOT_FOUND'})); sys.exit(1)
    rows = [ClosingRow(line=r['line'], student_code=r['student_code'], bimester=r['bimester'],
        closing_date=date.fromisoformat(r['closing_date']), closing_available_at=datetime.fromisoformat(r['closing_available_at']),
        inputs=ClosingInputs(Decimal(r['average_grade']), r['days_scheduled'], r['days_attended'], r['activities_scheduled'],
            r['activities_delivered'], r['participation_level'], r['behavior_incidents'])) for r in p['rows']]
    try:
        print(json.dumps(load_closings(s, actor, UUID(p['period_id']), rows, uuid4())))
    except AppError as error:
        print(json.dumps({'code': error.code, 'details': error.details or []})); sys.exit(1)
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--period-id', required=True)
    parser.add_argument('--actor-email', required=True)
    parser.add_argument('--csv', type=Path, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from runtime_target import Target
    try:
        rows = parse_csv(args.csv)
        target = Target.load(args.target)
        if target.kind == 'ACTIVE':
            raise RuntimeError('ACTIVE_TARGET_FORBIDDEN')
        target.assert_identity()
        result = target.api_python(CODE, {'period_id': args.period_id, 'actor_email': args.actor_email, 'rows': rows})
    except (ClosingCsvError, RuntimeError) as error:
        print(json.dumps({'code': str(error)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
