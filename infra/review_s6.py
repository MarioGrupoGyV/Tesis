"""Revisión S6 contra destino explícito; ningún fallback ni preparación del activo."""
import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import UUID

from review_accounts import credentials
from runtime_target import ROOT, TABLES, Target


SNAPSHOT = '''
import hashlib,json,sys
from pathlib import Path
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
payload=json.load(sys.stdin)
database=Database(Settings())
with database.engine.connect() as c:
 tables=c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='risk_school' ORDER BY table_name")).scalars().all()
 assert tables==payload['tables']
 counts={};fingerprints={};row_ids={};old={}
 for table in tables:
  rows=c.execute(text('SELECT row_to_json(x)::text FROM risk_school.'+table+' x ORDER BY id')).scalars().all()
  counts[table]=len(rows)
  fingerprints[table]=hashlib.sha256(''.join(rows).encode()).hexdigest()
  if table in ('audit_events','user_sessions'):
   row_ids[table]=c.execute(text('SELECT id::text FROM risk_school.'+table+' ORDER BY id')).scalars().all()
   if table in payload.get('old_ids',{}):
    prior=c.execute(text('SELECT row_to_json(x)::text FROM risk_school.'+table+' x WHERE id=ANY(CAST(:ids AS uuid[])) ORDER BY id'),{'ids':payload['old_ids'][table]}).scalars().all()
    old[table]={'count':len(prior),'sha256':hashlib.sha256(''.join(prior).encode()).hexdigest()}
 files={}
 for key,root in [('imports',Path('/var/lib/riesgo/imports')),('ml',Path('/var/lib/riesgo/ml'))]:
  files[key]=sorted((str(p.relative_to(root)),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob('*') if p.is_file())
print(json.dumps({'counts':counts,'fingerprints':fingerprints,'row_ids':row_ids,'old':old,'files':files}))
database.engine.dispose()
'''


def public_target(target):
    return {key: target.data[key] for key in ('kind', 'project', 'database', 'target_id', 'web_url', 'api_url', 'ports', 'volumes', 'images')}


def snapshot(target, before=None):
    return target.api_python(SNAPSHOT, {'tables': sorted(TABLES), 'old_ids': before['row_ids'] if before else {}})


def describe(target, account, study_id, period_id):
    # El hook histórico se incorpora solo en memoria. Únicamente describe: no
    # identity test-only, revision, bootstrap ni generador sobre esta revisión.
    source = (ROOT / 'backend/tests/browser_fixture.py').read_text(encoding='utf-8')
    code = "import json,sys\npayload=json.load(sys.stdin)\nnamespace={'__name__':'s6_private_describe','__file__':'/app/browser_fixture.py'}\nexec(" + repr(source) + ",namespace)\n"
    code += '''
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
database=Database(Settings())
with database.engine.connect() as db:
 study=db.execute(text('SELECT id::text,period_id::text,csv_sha256 FROM risk_school.synthetic_studies WHERE id=CAST(:id AS uuid)'),{'id':payload['study_id']}).mappings().one()
 assert study['period_id']==payload['period_id']
 batch=db.execute(text("SELECT id::text FROM risk_school.import_batches WHERE period_id=CAST(:id AS uuid) AND status='COMMITTED' ORDER BY created_at LIMIT 1"),{'id':payload['period_id']}).scalar_one()
result=namespace['browser_action']({**payload,'action':'describe'})
result.update(study_id=payload['study_id'],import_id=batch,csv_sha256=study['csv_sha256'])
print(json.dumps(result))
database.engine.dispose()
'''
    return target.api_python(code, {**account, 'study_id': str(study_id), 'period_id': str(period_id)})


def validate_prefix(prefix):
    if not re.fullmatch(r's6[a-z0-9-]+', prefix):
        raise RuntimeError('S6_EVIDENCE_PREFIX_INVALID')
    if any((ROOT / 'tests/evidence' / (prefix + ending)).exists() for ending in
           ('-environment.json', '-playwright.json', '-response-samples.json', '-infrastructure-failure.json')):
        raise RuntimeError('S6_EVIDENCE_EXISTS')


def playwright(target, accounts, study, prefix, phase, *options):
    target.assert_identity()
    if not target.path:
        raise RuntimeError('S6_TARGET_DESCRIPTOR_REQUIRED')
    env = {**os.environ, 'E2E_BASE_URL': target.web_url, 'E2E_SCOPE': target.kind,
           'E2E_TARGET': json.dumps(public_target(target)), 'E2E_TARGET_FILE': str(target.path),
           'E2E_ACCOUNTS': json.dumps(accounts), 'E2E_STUDY': json.dumps(study),
           'E2E_EVIDENCE_PREFIX': prefix, 'E2E_PHASE': phase,
           'E2E_REPORT_FILE': f'tests/evidence/{prefix}-playwright.json'}
    command = ['cmd', '/c', 'npx', 'playwright', 'test'] if os.name == 'nt' else ['npx', 'playwright', 'test']
    subprocess.run([*command, *options], cwd=ROOT, env=env, check=True)


def review(target, prefix, study_id, period_id, *, accounts=None, outage=False):
    validate_prefix(prefix)
    if target.kind not in ('ACTIVE', 'RESTORE', 'INSTALL'):
        raise RuntimeError('S6_REVIEW_TARGET_INVALID')
    if outage and target.kind == 'ACTIVE':
        raise RuntimeError('S6_ACTIVE_OUTAGE_FORBIDDEN')
    target.assert_identity()
    before = snapshot(target)
    if accounts is None:
        if target.kind == 'INSTALL':
            raise RuntimeError('S6_INSTALLATION_ACCOUNTS_REQUIRED_IN_MEMORY')
        accounts = credentials()  # Solo lectura de las cuatro entradas originales.
    study = describe(target, accounts['ADMIN'], study_id, period_id)
    began = datetime.now(UTC).isoformat()
    success = False
    try:
        playwright(target, accounts, study, prefix, 's6-review')
        if outage:
            outage_prefix = prefix + '-outage'
            validate_prefix(outage_prefix)
            playwright(target, accounts, study, outage_prefix, 's6-outage')
        success = True
    finally:
        after = snapshot(target, before)
        protected = [table for table in TABLES if table not in ('user_sessions', 'audit_events')]
        data_preserved = all(before['fingerprints'][table] == after['fingerprints'][table] for table in protected)
        files_preserved = before['files'] == after['files']
        previous_access_preserved = all(after['old'][table] == {'count': before['counts'][table], 'sha256': before['fingerprints'][table]}
                                        for table in ('user_sessions', 'audit_events'))
        report = {'status': 'COMPROBADO' if success and data_preserved and files_preserved and previous_access_preserved else 'FALLIDO',
                  'target': public_target(target), 'started_at': began, 'finished_at': datetime.now(UTC).isoformat(),
                  'counts_before': before['counts'], 'counts_after': after['counts'],
                  'protected_table_fingerprints_preserved': data_preserved, 'private_file_hashes_preserved': files_preserved,
                  'previous_sessions_audit_rows_preserved': previous_access_preserved,
                  'new_sessions': after['counts']['user_sessions'] - before['counts']['user_sessions'],
                  'new_audit_events': after['counts']['audit_events'] - before['counts']['audit_events'],
                  'human_followup_mutations': False, 'regenerated_or_retrained': False,
                  'verification_changes': 'Sesiones y auditoría nuevas de acceso, cierre, exportación y reutilización.',
                  'real_postgresql_outage': bool(outage)}
        (ROOT / f'tests/evidence/{prefix}-environment.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        assert data_preserved and files_preserved and previous_access_preserved, 'S6_REVIEW_PREVIOUS_EVIDENCE_CHANGED'
    return report


def control_db(target, action):
    if target.kind not in ('INSTALL', 'RESTORE'):
        raise RuntimeError('S6_ACTIVE_DATABASE_CONTROL_FORBIDDEN')
    if action == 'stop':
        target.assert_identity()
        target.compose('stop', 'db')
    else:
        target.assert_resources()
        target.compose('up', '-d', '--wait', 'db')
        target.assert_identity()


def control_period(target, period_id, action):
    if target.kind != 'INSTALL':
        raise RuntimeError('S6_PERIOD_FIXTURE_ONLY_INSTALLATION')
    code = '''
import json,sys
from uuid import UUID,uuid4
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
from app.models.s1 import AuditEvent
payload=json.load(sys.stdin)
database=Database(Settings())
with database.session_factory() as db:
 period=UUID(payload['period_id'])
 row=db.execute(text("SELECT is_locked FROM risk_school.academic_periods WHERE id=:id AND data_origin='SYNTHETIC' FOR UPDATE"),{'id':period}).one()
 expected=payload['action']=='unlock'
 assert row.is_locked==expected
 db.execute(text('UPDATE risk_school.academic_periods SET is_locked=:locked WHERE id=:id'),{'locked':not expected,'id':period})
 db.add(AuditEvent(actor_id=None,entity_type='ACADEMIC_PERIOD',entity_id=period,action='S6_ISOLATED_PERIOD_LOCK_FIXTURE',request_id=uuid4(),payload={'isolated_test_only':True,'is_locked':not expected}))
 db.commit()
print(json.dumps({'period_id':str(period),'is_locked':not expected,'scope':'INSTALL_ONLY'}))
database.engine.dispose()
'''
    return target.api_python(code, {'period_id': str(period_id), 'action': action})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--study-id', type=UUID)
    parser.add_argument('--period-id', type=UUID)
    parser.add_argument('--prefix')
    parser.add_argument('--outage', action='store_true', help='Fallo real de DB exclusivamente aislado; siempre se reanuda.')
    parser.add_argument('--control-db', choices=['stop', 'start'], help='Coordinación privada de la prueba Playwright aislada.')
    parser.add_argument('--control-period', choices=['lock', 'unlock'], help='Fixture real de bloqueo exclusivamente en instalación nueva.')
    args = parser.parse_args(argv)
    try:
        target = Target.load(args.target)
        if args.control_db:
            control_db(target, args.control_db)
            print(json.dumps({'status': 'COMPROBADO', 'action': args.control_db, 'project': target.project}))
        elif args.control_period:
            if not args.period_id:
                parser.error('--period-id requerido para fixture aislado')
            print(json.dumps(control_period(target, args.period_id, args.control_period)))
        else:
            if not args.study_id or not args.period_id or not args.prefix:
                parser.error('--study-id, --period-id y --prefix requeridos para revisión')
            result = review(target, args.prefix, args.study_id, args.period_id, outage=args.outage)
            print(json.dumps({'status': result['status'], 'target': result['target']}))
    except (RuntimeError, ValueError, OSError, AssertionError, subprocess.CalledProcessError) as error:
        code = str(error) if isinstance(error, RuntimeError) and re.fullmatch(r'[A-Z0-9_]{1,100}', str(error)) else 'S6_REVIEW_FAILED'
        print(json.dumps({'code': code})); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
