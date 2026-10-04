"""Genera secretos solo de desarrollo, sin mostrarlos ni reemplazar los existentes."""
from pathlib import Path
import json
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / '.local/secrets'
    directory.mkdir(parents=True, exist_ok=True)
    names = ['owner-password', 'app-password', 'csrf-secret', 'app-database-url',
             'owner-database-url', 'demo-credentials.json']
    existing = [(directory / name).exists() for name in names]
    if any(existing):
        if not all(existing):
            raise SystemExit('Secretos incompletos: conservar los existentes y revisar .local/secrets.')
        print('Configuración DEMO ya preparada; secretos conservados.')
        return
    owner, app = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    values = {
        'owner-password': owner, 'app-password': app, 'csrf-secret': secrets.token_urlsafe(48),
        'app-database-url': f'postgresql+psycopg://riesgo_app:{app}@db:5432/riesgo_escolar_demo',
        'owner-database-url': f'postgresql+psycopg://riesgo_owner:{owner}@db:5432/riesgo_escolar_demo',
        'demo-credentials.json': json.dumps({role: {
            'email': f'{role}@demo.example.org', 'password': secrets.token_urlsafe(20)
        } for role in ('admin', 'tutor', 'director')}, indent=2),
    }
    for name, content in values.items():
        path = directory / name
        with path.open('x', encoding='utf-8', newline='\n') as file:
            file.write(content + '\n')
        if os.name != 'nt':
            path.chmod(0o600)
    print('Configuración DEMO generada en .local/secrets (excluida de Git). No se muestran contraseñas.')


if __name__ == '__main__':
    main()
