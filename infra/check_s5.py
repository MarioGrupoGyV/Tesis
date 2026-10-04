"""Cierre S5 sobre base poblada: conservación histórica y evidencia efectiva."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import yaml
from jsonschema import Draft202012Validator,FormatChecker
from runtime_snapshot import ROOT,snapshot,SCHOOL

INITIAL='e9349f26b3f0b301cd4d5f50bbec0a7532110e85'

def command(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True,encoding='utf-8').strip()

def read(name):
    return json.loads((ROOT/'tests/evidence'/name).read_text(encoding='utf-8'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend-prefix',default='s5-backend-final')
    parser.add_argument('--isolated-prefix',default='s5-complete-final')
    parser.add_argument('--active-prefix',default='s5-active-final')
    args=parser.parse_args()
    assert all(re.fullmatch(r's5[A-Za-z0-9-]*',p) for p in vars(args).values())
    before=json.loads((ROOT/'.local/s5-before.json').read_text(encoding='utf-8'))
    after=snapshot()
    protected=[table for table in SCHOOL if table not in ('alerts','interventions','followup_decisions')]
    assert all(before['fingerprints'][t]==after['fingerprints'][t] for t in protected)
    assert before['files']==after['files'] and before['ml_files']==after['ml_files']
    assert before['users']==after['users'] and before['fingerprints']['app_users']==after['fingerprints']['app_users']
    assert len(after['counts'])==15 and after['counts']['students']==60 and after['counts']['academic_snapshots']==360 and after['counts']['predictions']==55
    assert after['counts']['followup_decisions']==55 and after['counts']['alerts']>0
    # Solo dos actividades de simulación y un caso cerrado en revisión activa.
    assert after['counts']['interventions']==2
    old_code="""
import json,sys
from sqlalchemy import text
from app.core.database import Database
from app.core.config import Settings
counts=json.load(sys.stdin)
with Database(Settings()).engine.connect() as c:
 assert c.scalar(text('SELECT current_user'))=='riesgo_app'
 times={'user_sessions':'created_at','audit_events':'recorded_at'}
 result={t:c.scalar(text("SELECT md5(coalesce(string_agg(row_to_json(x)::text,'' ORDER BY id),'')) FROM (SELECT * FROM risk_school."+t+" ORDER BY "+times[t]+",id LIMIT :n) x"),{'n':n}) for t,n in counts.items()}
 print(json.dumps(result))
"""
    old=subprocess.run(['docker','compose','exec','-T','api','python','-c',old_code],cwd=ROOT,
        input=json.dumps({t:before['counts'][t] for t in ('user_sessions','audit_events')}),capture_output=True,text=True,encoding='utf-8',check=True)
    assert all(value==before['fingerprints'][t] for t,value in json.loads(old.stdout).items())
    tracked=command('git','ls-tree','-r','--name-only',INITIAL).splitlines()
    locks=['backend/requirements.in','backend/requirements.txt','backend/requirements-dev.in','backend/requirements-dev.txt',
        'infra/requirements-s0.in','infra/requirements-s0.txt','package.json','package-lock.json','frontend/package.json','infra/windows_credentials.py']
    preserved=[name for name in tracked if name.startswith(('tests/evidence/','docs/adr/','backend/app/ml/','backend/migrations/')) or
        re.search(r'docs/planning/(Estado_Sprint_|Matriz_verificacion_)',name) or name in locks]
    for name in preserved:
        prior=subprocess.check_output(['git','show',INITIAL+':'+name],cwd=ROOT)
        current=(ROOT/name).read_bytes()
        if Path(name).suffix.lower() not in ('.png','.jpg','.jpeg','.pdf'):
            prior,current=prior.replace(b'\r\n',b'\n'),current.replace(b'\r\n',b'\n')
        assert prior==current,name
    contract=yaml.safe_load((ROOT/'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    assert contract['info']['version']=='0.5.0'
    routes_code="import json; from app.main import create_app; print(json.dumps(sorted((m.upper(),p,o['operationId']) for p,ops in create_app().openapi()['paths'].items() for m,o in ops.items() if m in ('get','post','patch'))))"
    routes=json.loads(command('docker','compose','exec','-T','api','python','-c',routes_code))
    normalize=lambda p:re.sub(r'\{[^}]+\}','{}',p)
    assert len(routes)==27
    assert {(m,normalize(p),id) for m,p,id in routes}=={(m.upper(),normalize('/api/v1'+p),o['operationId']) for p,ops in contract['paths'].items() for m,o in ops.items() if m in ('get','post','patch')}
    assert '/models/{id}/activate' not in contract['paths']
    samples=read('s5-response-samples.json')
    schemas=set()
    for sample in samples:
        Draft202012Validator({'$ref':'#/components/schemas/'+sample['schema'],'components':contract['components']},format_checker=FormatChecker()).validate(sample['body'])
        schemas.add(sample['schema'])
    assert {'FollowupResult','AlertPage','AlertDetail','InterventionCreateResult','InterventionView','ReportSummary','PredictionRunResult','Error'}<=schemas
    suites=list(ET.parse(ROOT/'tests/evidence'/f'{args.backend_prefix}.xml').getroot().iter('testsuite'))
    assert suites and all(int(s.attrib.get(k,0))==0 for s in suites for k in ('failures','errors','skipped'))
    environment=read(f'{args.backend_prefix}-environment.json')
    assert environment['status']=='COMPROBADO' and environment['python']=='3.12.12' and environment['platform']=='Linux'
    browsers={'isolated':read(args.isolated_prefix+'-playwright.json'),'active':read(args.active_prefix+'-playwright.json'),
        'first_import':read(args.isolated_prefix+'-import-playwright.json')}
    for label,report in browsers.items():
        assert report['status']=='passed' and report['cases'],label
        allowed={'passed','skipped'} if label=='active' else {'passed'}
        assert all(c['status'] in allowed for c in report['cases']),label
        assert sum(c['status']=='passed' for c in report['cases']) >= (4 if label=='active' else 1),label
    isolated=read(args.isolated_prefix+'-environment.json');active=read(args.active_prefix+'-environment.json')
    assert isolated['status']=='COMPROBADO' and isolated['active_environment_untouched'] and isolated['complete_followup_via_real_browser_api']
    assert active['status']=='COMPROBADO' and active['academic_model_predictions_and_private_files_preserved'] and active['users_preserved'] and not active['regenerated_or_retrained']
    persistence=read('s5-persistence.json')
    assert persistence['status']=='COMPROBADO' and persistence['all_tables_users_credentials_audit_files_identical_after_recreation']
    assert len(persistence['counts_after_recreation'])==15
    static=read('s5-contracts.json');assert static['status']=='COMPROBADO' and static['api_operations']==27
    build=read('s5-build.json');assert build['status']=='COMPROBADO'
    containers=json.loads(command('docker','inspect','riesgo-escolar-api-1','riesgo-escolar-web-1','riesgo-escolar-db-1'))
    assert all(c['State']['Health']['Status']=='healthy' for c in containers)
    api=next(c for c in containers if c['Name']=='/riesgo-escolar-api-1')
    assert {m.get('Name') for m in api['Mounts'] if m.get('Type')=='volume'}=={'riesgo-escolar_import_data','riesgo-escolar_ml_data'}
    pip=command('docker','compose','exec','-T','api','python','-m','pip','check');assert pip=='No broken requirements found.'
    old_environment=json.loads(command('docker','inspect','riesgo-escolar-demo-api-1','riesgo-escolar-demo-web-1','riesgo-escolar-demo-db-1'))
    assert all(not c['State']['Running'] for c in old_environment)
    backup=read('s2-1-backup.json')
    assert all(hashlib.sha256((Path(backup['backup_private_path'])/name).read_bytes()).hexdigest()==value for name,value in backup['hashes'].items())
    report={'status':'COMPROBADO','initial_sha':INITIAL,'final_head':command('git','rev-parse','HEAD'),
        'counts_before':before['counts'],'counts_after':after['counts'],
        'academic_records_model_predictions_and_files_preserved':True,'accounts_and_prior_sessions_audit_preserved':True,
        'backend_tests':sum(int(s.attrib['tests']) for s in suites),'validated_contract_responses':len(samples),
        'api_operations':len(routes),'registered_operations':routes,'browser_prefixes':vars(args),
        'browser_cases':{label:{'passed':sum(c['status']=='passed' for c in report['cases']),
                               'skipped':sum(c['status']=='skipped' for c in report['cases'])} for label,report in browsers.items()},
        'preserved_files':preserved,'locks_unchanged':True,'ml_math_and_old_migrations_unchanged':True,
        'backup_hashes_match':True,'historical_environment_stopped':True,'pip_check':pip,
        'images':{c['Name'].lstrip('/'):c['Image'] for c in containers},
        'limits':['Seguimiento operativo de simulación SYNTHETIC; REAL bloqueado','No eficacia escolar, validación de tesis ni S6',
                  'Simulaciones HTTP de fallos UI documentadas aparte','Sin commit, push o despliegue externo']}
    (ROOT/'tests/evidence/s5-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPROBADO S5: seguimiento/reportes, regresión, contrato, conservación y persistencia.')

if __name__=='__main__':main()
