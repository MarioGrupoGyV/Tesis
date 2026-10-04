"""Acción explícita S2.2: crea/reutiliza SOLO cuentas de revisión local autorizadas."""
import json
from pathlib import Path
import secrets
import subprocess
from windows_credentials import ROLES, read, write_new, target

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_NAMES = {role: {'email': f'revision.local.{role.lower()}@example.com',
    'display_name': f'Revisión local · {role}'} for role in ROLES}

# Secretos por stdin: jamás en código/argumentos, variables de Compose o archivos.
REMOTE = '''
import json, sys
from sqlalchemy import select, text
from app.core.config import Settings
from app.core.database import Database
from app.core.security import password_verify
from app.models.s1 import AppUser
from app.bootstrap_admin import AdministratorInput, create_first_admin
from app.configure_context import UserInput, configure
database=Database(Settings())
payload=json.load(sys.stdin)
with database.session_factory() as db:
 assert db.scalar(text('SELECT current_user'))=='riesgo_app'
 assert db.scalar(text('SELECT current_database()'))=='riesgo_escolar'
 if payload['action']=='inspect':
  users=db.scalars(select(AppUser).order_by(AppUser.role,AppUser.id)).all()
  print(json.dumps([{'id':str(u.id),'email':u.email,'display_name':u.display_name,'role':u.role,'is_active':u.is_active} for u in users]))
 else:
  result=[]
  credentials=payload['accounts']
  admin_data=credentials['ADMIN']
  admin=db.scalar(select(AppUser).where(AppUser.role=='ADMIN').order_by(AppUser.created_at).limit(1))
  created=False
  if admin is None:
   identifier=create_first_admin(db, AdministratorInput(**admin_data))
   admin=db.get(AppUser,identifier)
   created=True
  if not admin.is_active or admin.email!=admin_data['email'] or not password_verify(admin_data['password'],admin.password_hash):
   raise RuntimeError('Administrador existente no coincide con acceso autorizado; no se modifica.')
  result.append({'id':str(admin.id),'email':admin.email,'role':'ADMIN','created':created})
  for role in ('TUTOR','DIRECTOR','RESEARCHER'):
   values=credentials[role]
   existing=db.scalar(select(AppUser).where(AppUser.email==values['email']))
   created=False
   if existing is None:
    identifier=configure(db,admin,UserInput(**values,role=role))
    existing=db.get(AppUser,identifier)
    created=True
   if existing.role!=role or not existing.is_active or not password_verify(values['password'],existing.password_hash):
    raise RuntimeError('Cuenta existente incompatible; no se restablece ni cambia su rol.')
   result.append({'id':str(existing.id),'email':existing.email,'role':role,'created':created})
  print(json.dumps(result))
'''

def remote(payload):
    result = subprocess.run(['docker','compose','exec','-T','api','python','-c',REMOTE],cwd=ROOT,
        input=json.dumps(payload),text=True,encoding='utf-8',stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:
        # No imprimir excepciones que pudieran contener valores de validación.
        raise RuntimeError('La preparación no pudo completarse; se conservan cuentas/credenciales. Revisa identidad, permisos y servicios.')
    return json.loads(result.stdout)

def credentials():
    accounts = {}
    for role in ROLES:
        value = read(role)
        if value is None:
            raise RuntimeError('Falta entrada privada para '+role+'; ejecuta primero review_accounts.py.')
        accounts[role] = value
    assert len({a['password'] for a in accounts.values()}) == len(ROLES)
    assert all(len(a['password']) >= 20 for a in accounts.values())
    return accounts

def main():
    existing = remote({'action':'inspect'})
    admin = next((u for u in existing if u['role']=='ADMIN'),None)
    stored_admin = read('ADMIN')
    if admin and (not stored_admin or stored_admin['email']!=admin['email']):
        raise SystemExit('Ya existe un administrador sin acceso disponible en el almacén privado. Se conserva; el operador debe proporcionar acceso autorizado.')
    values = {}
    for role in ROLES:
        public = PUBLIC_NAMES[role]
        stored = read(role)
        if stored is None:
            if any(u['email']==public['email'] for u in existing):
                raise SystemExit('Cuenta existente sin credencial privada disponible; no se modifica.')
            write_new(role,public['email'],secrets.token_urlsafe(30))
            stored = read(role)
        values[role] = {**public,**stored}
    result = remote({'action':'prepare','accounts':values})
    report = {'status':'COMPROBADO','scope':'explicit_local_access_only','initial_users':existing,
        'accounts':[{**u,'credential_target':target(u['role'])} for u in result],
        'password_store':'Windows Credential Manager; current Windows user','school_records_created':False}
    path=ROOT/'tests/evidence/s2-2-accounts.json'
    if path.exists():
        path=ROOT/'tests/evidence/s2-2-accounts-repeat.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))

if __name__=='__main__':
    main()
