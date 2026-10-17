"""Recorrido M1 aislado con cuentas aleatorias en memoria. Sin acceso al activo."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
from runtime_target import Target,ROOT,write_new
from windows_dpapi import protect,unprotect

PREPARE='''
import json,sys
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
from app.core.security import password_hash
from app.models.s1 import AppUser
p=json.load(sys.stdin)
db=Database(Settings())
with db.session_factory() as s:
 assert s.scalar(text('SELECT current_user'))=='riesgo_app'
 assert s.scalar(text('SELECT current_database()')).startswith('s6_install_')
 assert s.scalar(text('SELECT count(*) FROM risk_school.app_users'))==0
 for role,account in p['accounts'].items():
  s.add(AppUser(email=account['email'],display_name='Prueba M1 '+role,role='TUTOR' if role=='TUTOR_OTHER' else role,password_hash=password_hash(account['password'])))
 s.commit()
print(json.dumps({'prepared':True}))
'''

SNAPSHOT='''
import json,hashlib
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
db=Database(Settings())
with db.engine.connect() as s:
 assert s.scalar(text('SELECT current_user'))=='riesgo_app'
 assert s.scalar(text('SELECT current_database()')).startswith('s6_install_')
 tables=['students','enrollments','academic_snapshots','audit_events','predictions','model_versions','alerts','interventions']
 counts={t:s.scalar(text('SELECT count(*) FROM risk_school.'+t)) for t in tables}
 digests={t:s.scalar(text("SELECT md5(coalesce(string_agg(to_jsonb(x)::text,'|' ORDER BY id),'')) FROM risk_school."+t+" x")) for t in tables}
print(json.dumps({'counts':counts,'digests':digests,'database_role':'riesgo_app'}))
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--prefix',default='m1-browser-first')
    args=parser.parse_args()
    if not args.prefix.startswith('m1-') or not args.prefix.replace('-','').isalnum():
        raise RuntimeError('M1_PREFIX_INVALID')
    target=Target.load(args.target)
    if target.kind!='INSTALL' or target.web_url!='http://localhost:15275':
        raise RuntimeError('M1_ISOLATED_INSTALL_REQUIRED')
    target.assert_identity()
    account_file=target.path.with_suffix('.m1-accounts.dpapi')
    accounts=json.loads(unprotect(account_file.read_bytes())) if account_file.exists() else {
        role:{'email':f'm1-{role.lower()}@example.com','password':secrets.token_urlsafe(24)}
        for role in ('ADMIN','TUTOR','DIRECTOR','RESEARCHER','TUTOR_OTHER')}
    # Esquema del fixture privado no añade cuentas al producto ni Credential Manager.
    if not account_file.exists():
        target.api_python(PREPARE,{'accounts':accounts})
        write_new(account_file,protect(json.dumps(accounts).encode()))
    environment={**os.environ,'M1_BASE':target.web_url,'M1_ACCOUNTS':json.dumps(accounts),'M1_PREFIX':args.prefix,
        'M1_REPORT':f'tests/evidence/{args.prefix}.json'}
    result=subprocess.run(['cmd','/c','npx','playwright','test','--config','playwright.m1.config.ts'],cwd=ROOT,env=environment)
    if result.returncode:
        raise RuntimeError('M1_BROWSER_FAILED')
    before=target.api_python(SNAPSHOT,{})
    target.compose('up','-d','--wait','--force-recreate',capture_output=True)
    target.assert_identity()
    after=target.api_python(SNAPSHOT,{})
    assert before==after,'M1_RECREATION_PERSISTENCE_FAILED'
    assert after['counts']['academic_snapshots']>=2
    assert all(after['counts'][t]==0 for t in ('predictions','alerts','interventions','model_versions'))
    write_new(ROOT/f'tests/evidence/{args.prefix}-persistence.json',json.dumps({'status':'COMPROBADO',
        'project':target.project,'database':target.database,'web_url':target.web_url,'volumes':target.data['volumes'],
        'before':before,'after':after,'services_recreated_without_volume_deletion':True},indent=2).encode())
    print(json.dumps({'status':'COMPROBADO','project':target.project,'counts':after['counts']}))


if __name__=='__main__':
    main()
