"""Solo runner aislado: crea una DB nueva y cuenta efímera; nunca la aplicación activa."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.bootstrap_admin import AdministratorInput, BootstrapError, create_first_admin
from app.configure_context import UserInput, configure
from app.models.s1 import AppUser

def main():
    owner = make_url(Path('/run/secrets/owner_url').read_text().strip()).set(host='dbtest', port=5432, database='riesgo_escolar_test')
    app = make_url(Path('/run/secrets/app_url').read_text().strip()).set(host='dbtest', port=5432)
    name = 'riesgo_escolar_test_browser_' + uuid4().hex[:12]
    engine = create_engine(owner, isolation_level='AUTOCOMMIT', hide_parameters=True)
    with engine.connect() as db:
        db.exec_driver_sql(f'CREATE DATABASE {name} OWNER riesgo_owner')
        db.exec_driver_sql(f'REVOKE ALL ON DATABASE {name} FROM PUBLIC')
        db.exec_driver_sql(f'GRANT CONNECT ON DATABASE {name} TO riesgo_app')
    engine.dispose()
    app, owner = app.set(database=name), owner.set(database=name)
    os.environ['MIGRATION_DATABASE_URL'] = owner.render_as_string(hide_password=False)
    subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],check=True,stdout=sys.stderr)
    email, password = 'browser-'+uuid4().hex+'@example.com', secrets.token_urlsafe(24)
    engine = create_engine(app, hide_parameters=True)
    with Session(engine) as db:
        assert db.scalar(text('SELECT current_user')) == 'riesgo_app'
        assert db.scalar(text('SELECT count(*) FROM risk_school.app_users')) == 0
        values = AdministratorInput(email=email, display_name='Prueba aislada de acceso', password=password)
        create_first_admin(db, values)
        try:
            create_first_admin(db, values)
            raise AssertionError('El bootstrap no rechazó repetición')
        except BootstrapError:
            pass
        accounts = {'ADMIN': {'email':email,'password':password}}
        admin = db.scalar(text("SELECT id FROM risk_school.app_users WHERE role='ADMIN'"))
        admin = db.get(AppUser, admin)
        for role in ('TUTOR','DIRECTOR','RESEARCHER'):
            account = {'email':f'browser-{role.lower()}-{uuid4().hex}@example.com','password':secrets.token_urlsafe(24)}
            configure(db,admin,UserInput(**account,display_name=f'Acceso aislado {role}',role=role))
            accounts[role] = account
    engine.dispose()
    # El padre captura esta salida en memoria; no se muestra ni se escribe el password.
    print(json.dumps({'database_url':app.render_as_string(hide_password=False),'accounts':accounts,'database':name}))

if __name__ == '__main__':
    main()
