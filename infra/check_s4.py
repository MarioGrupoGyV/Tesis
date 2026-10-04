"""Cierre S4: lecturas sobre contexto poblado y evidencias nuevas, sin base vacía."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from runtime_snapshot import ROOT, snapshot, school_unchanged

INITIAL='90a5e8492b9bdd7d1a37ae59e105fddbd7e116a7'
def command(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True,encoding='utf-8').strip()
def read(name):
    return json.loads((ROOT/'tests/evidence'/name).read_text(encoding='utf-8'))
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--isolated-prefix',default='s4-complete')
    parser.add_argument('--active-prefix',default='s4-active-complete')
    args=parser.parse_args()
    assert all(re.fullmatch(r's4[A-Za-z0-9-]*',p) for p in (args.isolated_prefix,args.active_prefix))
    before=json.loads((ROOT/'.local/s4-before.json').read_text(encoding='utf-8'))
    after=snapshot()
    assert school_unchanged(before,after) and before['users']==after['users']
    assert before['fingerprints']['app_users']==after['fingerprints']['app_users']
    assert after['counts']['students']==60 and after['counts']['academic_snapshots']==360 and after['counts']['predictions']==55
    assert after['counts']['alerts']==after['counts']['interventions']==0
    prior_code="""
import json,sys
from sqlalchemy import text
from app.core.database import Database
from app.core.config import Settings
db=Database(Settings())
counts=json.load(sys.stdin)
with db.engine.connect() as c:
 assert c.scalar(text('SELECT current_user'))=='riesgo_app'
 times={'user_sessions':'created_at','audit_events':'recorded_at'}
 result={t:c.scalar(text("SELECT md5(coalesce(string_agg(row_to_json(x)::text,'' ORDER BY id),'')) FROM (SELECT * FROM risk_school."+t+" ORDER BY "+times[t]+",id LIMIT :n) x"),{'n':n}) for t,n in counts.items()}
 print(json.dumps(result))
"""
    old=subprocess.run(['docker','compose','exec','-T','api','python','-c',prior_code],cwd=ROOT,
        input=json.dumps({t:before['counts'][t] for t in ('user_sessions','audit_events')}),capture_output=True,text=True,encoding='utf-8',check=True)
    assert all(value==before['fingerprints'][name] for name,value in json.loads(old.stdout).items())
    tracked=command('git','ls-tree','-r','--name-only',INITIAL).splitlines()
    preserved=[name for name in tracked if name.startswith(('tests/evidence/','docs/adr/','backend/app/ml/','backend/migrations/')) or
        re.search(r'docs/planning/(Estado_Sprint_|Matriz_verificacion_)',name) or name in ('docs/planning/Contrato_API.yaml','docs/planning/Esquema.sql',
        'backend/requirements.in','backend/requirements.txt','backend/requirements-dev.in','backend/requirements-dev.txt',
        'infra/requirements-s0.in','infra/requirements-s0.txt','package.json','package-lock.json','frontend/package.json','infra/windows_credentials.py')]
    for name in preserved:
        old_content=subprocess.check_output(['git','show',INITIAL+':'+name],cwd=ROOT)
        current=(ROOT/name).read_bytes()
        if Path(name).suffix.lower() not in ('.png','.jpg','.jpeg','.pdf'):
            old_content,current=old_content.replace(b'\r\n',b'\n'),current.replace(b'\r\n',b'\n')
        assert old_content==current, name
    contract=yaml.safe_load((ROOT/'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    assert contract['info']['version']=='0.4.0'
    code="import json; from app.main import create_app; print(json.dumps(sorted((m.upper(),p) for p,ops in create_app().openapi()['paths'].items() for m in ops if m in ('get','post'))))"
    routes=json.loads(command('docker','compose','exec','-T','api','python','-c',code))
    normalize=lambda p:re.sub(r'\{[^}]+\}','{}',p)
    assert {(m,normalize(p)) for m,p in routes}=={(m.upper(),normalize('/api/v1'+p)) for p,ops in contract['paths'].items() for m in ops if m in ('get','post')}
    samples=read('s4-response-samples.json')+read('s4-ml-response-samples.json')
    for sample in samples:
        Draft202012Validator({'$ref':'#/components/schemas/'+sample['schema'],'components':contract['components']},format_checker=FormatChecker()).validate(sample['body'])
    suites=list(ET.parse(ROOT/'tests/evidence/s4-backend.xml').getroot().iter('testsuite'))
    assert suites and all(int(s.attrib.get(k,0))==0 for s in suites for k in ('failures','errors','skipped'))
    backend=read('s4-backend-environment.json')
    assert backend['status']=='COMPROBADO' and backend['platform']=='Linux' and backend['python']=='3.12.12'
    browsers={
        'first_import':read(args.isolated_prefix+'-isolated-import-playwright.json'),
        'isolated':read(args.isolated_prefix+'-isolated-playwright.json'),
        'active':read(args.active_prefix+'-playwright.json')}
    for label,report in browsers.items():
        assert report['status']=='passed' and report['cases'],label
        assert all(case['status']=='passed' for case in report['cases']),label
    isolated=read(args.isolated_prefix+'-browser-environment.json')
    active=read(args.active_prefix+'-environment.json')
    assert isolated['status']=='COMPROBADO' and isolated['first_import_via_real_browser_api']
    assert active['status']=='COMPROBADO' and active['school_and_private_files_unchanged'] and not active['regenerated_or_retrained']
    persistence=read('s4-persistence.json')
    assert persistence['status']=='COMPROBADO' and persistence['all_tables_users_credentials_audit_files_identical_after_recreation']
    static=read('s4-contracts.json'); assert static['status']=='COMPROBADO'
    builds=read('s4-build.json'); assert builds['status']=='COMPROBADO'
    exported=read('s4-csv-export.json')
    assert exported['status']=='COMPROBADO' and exported['registered_hash_identical'] and exported['existing_file_unchanged']
    assert exported['repeat_rejected']=='CSV_OUTPUT_EXISTS' and exported['output_outside_git'] and exported['temporary_file_removed']
    assert any(case.get('has_simulated_host_clock') for case in browsers['isolated']['cases'])
    assert any(case.get('has_simulated_host_clock') for case in browsers['active']['cases'])
    for label in ('isolated','active'):
        diagnostics=[item for case in browsers[label]['cases'] for item in case.get('real_intercepted_inference_diagnostics',[])]
        assert len(diagnostics)==2 and all(item['status']==200 and item['code'] is None for item in diagnostics),label
    containers=json.loads(command('docker','inspect','riesgo-escolar-api-1','riesgo-escolar-web-1','riesgo-escolar-db-1'))
    assert all(c['State']['Health']['Status']=='healthy' for c in containers)
    api=next(c for c in containers if c['Name']=='/riesgo-escolar-api-1')
    assert {m.get('Name') for m in api['Mounts'] if m.get('Type')=='volume'}=={'riesgo-escolar_import_data','riesgo-escolar_ml_data'}
    assert command('docker','compose','exec','-T','api','python','-m','pip','check')=='No broken requirements found.'
    old_env=json.loads(command('docker','inspect','riesgo-escolar-demo-api-1','riesgo-escolar-demo-web-1','riesgo-escolar-demo-db-1'))
    assert all(not c['State']['Running'] for c in old_env)
    backup=read('s2-1-backup.json')
    assert all(hashlib.sha256((Path(backup['backup_private_path'])/name).read_bytes()).hexdigest()==digest for name,digest in backup['hashes'].items())
    report={'status':'COMPROBADO','initial_sha':INITIAL,'final_sha':command('git','rev-parse','HEAD'),
        'backend_tests':sum(int(s.attrib['tests']) for s in suites),'validated_contract_responses':len(samples),
        'registered_routes':routes,'browser_reports':{label:{'cases':len(value['cases']),'status':value['status']} for label,value in browsers.items()},
        'browser_evidence_prefixes':vars(args),'counts':after['counts'],'academic_records_and_files_preserved':True,
        'accounts_password_hashes_preserved':True,'prior_sessions_and_audit_preserved':True,
        'preserved_files':preserved,'ml_and_migrations_unchanged':True,'backup_hashes_match':True,
        'historical_environment_stopped':True,'pip_check':'No broken requirements found.',
        'images':{c['Name'].lstrip('/'):c['Image'] for c in containers},
        'lock_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('backend/requirements.txt','backend/requirements-dev.txt','package-lock.json')},
        'limits':['REAL bloqueado; únicamente simulación SYNTHETIC','HTTP 503 simulado en navegador identificado aparte; integración positiva con API/DB real','S5/S6 e hipótesis institucional pendientes']}
    (ROOT/'tests/evidence/s4-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPROBADO S4: interfaz/API, estudio y cuentas preservados, contrato, regresión y persistencia.')
if __name__=='__main__': main()
