"""CLI interna: carga `identidades.local.csv` (student_code,full_name) a la FICHA de los alumnos REAL de un destino aislado.

    py -3.12 infra/load_identities.py --target <destino.json> --operator-profile <perfil> --csv <identidades.local.csv>
                                      [--confirm-active riesgo-escolar --pre-backup <respaldo .sebackup>]   (solo destino ACTIVE)

Solo ADMIN (perfil Windows existente, nunca contraseña en argumentos). Todo o nada; rechaza códigos desconocidos. Los nombres viajan por la
entrada estándar del proceso en el destino, no se imprimen y no se escriben en auditoría ni en registros (la auditoría guarda conteos).
Sobre el destino ACTIVE exige las mismas protecciones que la corrida real: `--confirm-active <proyecto>` y `--pre-backup` (respaldo S6 verificado de ese
proyecto, en 0009 y de menos de 24 h). Si no tienes el archivo, genéralo con el conversor: `convert_real_excel.py --identities`.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

HEADER = ('student_code', 'full_name')
MAX_ROWS = 2000

CODE = r'''
import json, sys
from sqlalchemy import select
from app.core.config import Settings
from app.core.database import Database
from app.core.errors import AppError
from app.models.s1 import AppUser
from app.services.identities import load_identities
p = json.load(sys.stdin)
db = Database(Settings())
with db.session_factory() as s:
    actor = s.scalar(select(AppUser).where(AppUser.email == p['actor_email'], AppUser.role == 'ADMIN', AppUser.is_active))
    if actor is None:
        print(json.dumps({'code': 'ACTOR_NOT_FOUND'})); sys.exit(1)
    try:
        print(json.dumps(load_identities(s, actor, [tuple(r) for r in p['rows']])))
    except AppError as error:
        print(json.dumps({'code': error.code, 'details': error.details or []})); sys.exit(1)
'''


class IdentitiesCsvError(ValueError):
    """Código estable sin valores del archivo."""


def parse_csv(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise IdentitiesCsvError('IDENTITIES_CSV_UNAVAILABLE')
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != HEADER:
            raise IdentitiesCsvError('IDENTITIES_CSV_HEADERS_INVALID')
        rows = []
        for line, values in enumerate(reader, start=2):
            if len(values) != 2 or not values[0].strip() or not values[1].strip():
                raise IdentitiesCsvError('IDENTITIES_CSV_ROW_INVALID:' + str(line))
            rows.append((line, values[0].strip(), values[1].strip()))
            if len(rows) > MAX_ROWS:
                raise IdentitiesCsvError('IDENTITIES_CSV_TOO_MANY_ROWS')
    if not rows:
        raise IdentitiesCsvError('IDENTITIES_CSV_EMPTY')
    return rows


def run(target, actor_email, csv_path, *, confirm_active=None, pre_backup=None):
    if target.kind == 'ACTIVE':
        import run_real_study as real      # una sola implementación de las protecciones: confirmación con el nombre del proyecto y respaldo previo
        try:
            real.guard_active(target.project, confirm_active, pre_backup)
        except real.StopRun as stop:
            raise RuntimeError(stop.code) from None
    rows = parse_csv(csv_path)
    target.assert_identity()
    return target.api_python(CODE, {'actor_email': actor_email, 'rows': rows})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--operator-profile', required=True)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--confirm-active', help='Solo destino ACTIVE: repite aquí el nombre del proyecto (riesgo-escolar)')
    parser.add_argument('--pre-backup', type=Path, help='Solo destino ACTIVE: respaldo S6 verificado (.sebackup), en 0009 y de menos de 24 h')
    args = parser.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        if not args.csv.is_file():
            print(json.dumps({'code': 'IDENTITIES_CSV_UNAVAILABLE',
                              'help': 'Genera el archivo con: py -3.12 infra/convert_real_excel.py --excel <libro> --out <carpeta fuera de Git> --identities'}))
            return 2
        from operator_profiles import admin_account
        from runtime_target import Target
        target = Target.load(args.target)
        account = admin_account(target, operator_profile=args.operator_profile)
        result = run(target, account['email'], args.csv, confirm_active=args.confirm_active, pre_backup=args.pre_backup)
    except (IdentitiesCsvError, RuntimeError) as error:
        print(json.dumps({'code': str(error).split(':')[0]}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
