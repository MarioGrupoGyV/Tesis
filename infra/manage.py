"""Operación Windows/PowerShell con Docker; conserva volúmenes."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    subprocess.run(['docker', *args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description='Preparación y operación de Seguimiento Escolar')
    parser.add_argument('command', choices=['prepare', 'up', 'migrate', 'bootstrap-admin', 'configure', 'restart', 'down'])
    args = parser.parse_args()
    if args.command in ('prepare', 'up'):
        subprocess.run([sys.executable, str(ROOT / 'infra/prepare.py')], check=True)
    if args.command == 'up':
        docker('compose', 'build', 'api', 'web')
        docker('compose', 'up', '-d', '--wait', 'db')
        migrate()
        docker('compose', 'up', '-d', '--wait', 'api', 'web')
    elif args.command == 'migrate':
        migrate()
    elif args.command == 'bootstrap-admin':
        docker('compose', 'exec', 'api', 'python', '-m', 'app.bootstrap_admin')
    elif args.command == 'configure':
        docker('compose', 'exec', 'api', 'python', '-m', 'app.configure_context')
    elif args.command == 'restart':
        docker('compose', 'restart', 'db', 'api', 'web')
    elif args.command == 'down':
        docker('compose', 'down')  # Sin -v: conserva el volumen.


def migrate():
    docker('compose', '-f', 'compose.yaml', '-f', 'infra/compose.migrate.yaml',
           'run', '--rm', '--no-deps', 'api', 'python', '-m', 'alembic',
           '-c', '/app/alembic.ini', 'upgrade', 'head')


if __name__ == '__main__':
    main()
