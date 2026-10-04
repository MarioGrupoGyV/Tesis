"""Prepara secretos de infraestructura; no crea cuentas ni registros escolares."""
from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / '.local/runtime-secrets'
    directory.mkdir(parents=True, exist_ok=True)
    names = ['owner-password', 'app-password', 'csrf-secret', 'app-database-url', 'owner-database-url']
    existing = [(directory/name).exists() for name in names]
    if any(existing):
        if not all(existing):
            raise SystemExit('Configuración parcial: conserva los archivos y revisa .local/runtime-secrets.')
        print('Secretos existentes conservados.')
        return
    owner, app = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    values = dict(zip(names, [owner, app, secrets.token_urlsafe(48),
        f'postgresql+psycopg://riesgo_app:{app}@db:5432/riesgo_escolar',
        f'postgresql+psycopg://riesgo_owner:{owner}@db:5432/riesgo_escolar'], strict=True))
    for name, value in values.items():
        with (directory/name).open('x', encoding='utf-8', newline='\n') as output:
            output.write(value+'\n')
        if os.name != 'nt':
            (directory/name).chmod(0o600)
    print('Secretos preparados; no se crearon cuentas ni datos escolares.')


if __name__ == '__main__':
    main()
