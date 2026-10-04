"""Cierre S3.1 sobre el contexto poblado: lectura y comprobaciones sanitizadas."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from runtime_snapshot import ROOT, snapshot

INITIAL = '412c370519900351f37bf2d444df9c943e58288d'


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8').strip()


def main():
    contract = yaml.safe_load((ROOT/'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    assert contract['info']['version'] == '0.4.0' and len(contract['paths']) == 19
    code = "import json; from app.main import create_app; print(json.dumps(sorted((m.upper(),p) for p,ops in create_app().openapi()['paths'].items() for m in ops if m in ('get','post'))))"
    routes = json.loads(output('docker','compose','exec','-T','api','python','-c',code))
    normalize = lambda p: re.sub(r'\{[^}]+\}', '{}', p)
    assert {(m,normalize(p)) for m,p in routes} == {(m.upper(),normalize('/api/v1'+p))
        for p,ops in contract['paths'].items() for m in ops if m in ('get','post')}
    active = json.loads((ROOT/'tests/evidence/s3-1-active-endpoints.json').read_text(encoding='utf-8'))
    assert active['status'] == 'COMPROBADO' and active['users_password_hashes_preserved']
    for case in active['cases']:
        assert case['result'] == 'COMPROBADO'
        path = case['path'].split('?')[0].removeprefix('/api/v1')
        key = path if path in contract['paths'] else next(p for p,ops in contract['paths'].items()
            if case['method'].lower() in ops and re.fullmatch(re.sub(r'\{[^}]+\}','[^/]+',p),path))
        response = contract['paths'][key][case['method'].lower()]['responses'][str(case['status'])]
        if case['response'] is not None:
            schema = {**response['content']['application/json']['schema'], 'components':contract['components']}
            Draft202012Validator(schema,format_checker=FormatChecker()).validate(case['response'])
    samples = json.loads((ROOT/'tests/evidence/s3-1-response-samples.json').read_text(encoding='utf-8'))
    samples += json.loads((ROOT/'tests/evidence/s3-1-ml-response-samples.json').read_text(encoding='utf-8'))
    for sample in samples:
        Draft202012Validator({'$ref':'#/components/schemas/'+sample['schema'], 'components':contract['components']},
            format_checker=FormatChecker()).validate(sample['body'])
    suite = ET.parse(ROOT/'tests/evidence/s3-1-backend.xml').getroot()
    suites = list(suite.iter('testsuite'))
    assert suites and all(int(s.attrib.get('failures',0)) == int(s.attrib.get('errors',0)) == 0 for s in suites)
    env = json.loads((ROOT/'tests/evidence/s3-1-backend-environment.json').read_text())
    assert env['status'] == 'COMPROBADO' and env['python'] == '3.12.12' and env['platform'] == 'Linux'
    persistence = json.loads((ROOT/'tests/evidence/s3-1-persistence.json').read_text())
    assert persistence['status'] == 'COMPROBADO' and persistence['all_tables_users_credentials_audit_files_identical_after_recreation']
    browser = {}
    for scope in ('active','isolated'):
        browser[scope] = json.loads((ROOT/f'tests/evidence/s3-1-{scope}-playwright.json').read_text())
        assert browser[scope]['status'] == 'passed' and len(browser[scope]['cases']) == 5
        assert all(case['status'] == 'passed' for case in browser[scope]['cases'])
    preserved = ['package.json','package-lock.json','frontend/package.json',
        'backend/requirements.in','backend/requirements.txt','backend/requirements-dev.in','backend/requirements-dev.txt',
        'infra/requirements-s0.in','infra/requirements-s0.txt','infra/check_runtime.py','infra/windows_credentials.py',
        'backend/migrations/versions/0001_demo_schema.py','backend/migrations/versions/0001_demo_schema.sql',
        'backend/migrations/versions/0002_institutional_boundary.py']
    historical = output('git','ls-tree','-r','--name-only',INITIAL,'tests/evidence','docs/planning','docs/adr').splitlines()
    preserved += [p for p in historical if p.startswith('tests/evidence/') or
        re.search(r'/(Estado_Sprint_|Matriz_verificacion_)',p) or p.startswith('docs/adr/')]
    for file in preserved:
        old = subprocess.check_output(['git','show',INITIAL+':'+file],cwd=ROOT)
        current = (ROOT/file).read_bytes()
        # Normalización exclusiva de CRLF de Windows, sin alterar archivos.
        if Path(file).suffix.lower() not in ('.png','.jpg','.jpeg','.gif','.pdf'):
            old,current = old.replace(b'\r\n',b'\n'),current.replace(b'\r\n',b'\n')
        assert old == current, file
    before = json.loads((ROOT/'.local/s3-1-before.json').read_text(encoding='utf-8'))
    after = snapshot()
    assert before['fingerprints']['app_users'] == after['fingerprints']['app_users'] and len(after['users']) == 4
    assert after['counts']['audit_events'] >= before['counts']['audit_events']
    assert all(item in after['files'] for item in before['files'])
    history_code = '''
import json
from sqlalchemy import text
from app.core.database import Database
from app.core.config import Settings
db=Database(Settings())
counts=json.loads(__import__('sys').stdin.read())
with db.engine.connect() as c:
 timestamps={'user_sessions':'created_at','audit_events':'recorded_at'}
 hashes={t:c.scalar(text("SELECT md5(coalesce(string_agg(row_to_json(x)::text,'' ORDER BY id),'')) FROM (SELECT * FROM risk_school."+t+" ORDER BY "+timestamps[t]+",id LIMIT :n) x"),{'n':n}) for t,n in counts.items()}
 print(json.dumps(hashes))
'''
    old_records = subprocess.run(['docker','compose','exec','-T','api','python','-c',history_code],cwd=ROOT,
        input=json.dumps({t:before['counts'][t] for t in ('user_sessions','audit_events')}),
        capture_output=True,text=True,encoding='utf-8',check=True)
    old_hashes = json.loads(old_records.stdout)
    assert all(old_hashes[t] == before['fingerprints'][t] for t in old_hashes)
    check = '''
import json
from sqlalchemy import text
from app.core.database import Database
from app.core.config import Settings
db=Database(Settings())
with db.engine.connect() as c:
 assert c.scalar(text('SELECT current_user'))=='riesgo_app'
 assert c.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='risk_school' AND table_name='synthetic_studies'"))==1
 assert c.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='synthetic_only_active_model'"))==1
 names=('academic_periods','students','enrollments','import_batches','academic_snapshots','model_versions','predictions','alerts','interventions')
 origins={n:dict(c.execute(text('SELECT data_origin,count(*) FROM risk_school.'+n+' GROUP BY data_origin')).all()) for n in names}
 assert all(set(v)<= {'SYNTHETIC'} for v in origins.values()), 'Contexto activo inesperado'
 assert c.scalar(text("SELECT count(*) FROM risk_school.model_versions WHERE is_active AND data_origin!='SYNTHETIC'"))==0
 assert c.scalar(text('SELECT count(*) FROM risk_school.alerts'))==c.scalar(text('SELECT count(*) FROM risk_school.interventions'))==0
 print(json.dumps({'role':'riesgo_app','schema_contract':'0003_synthetic_study','origins':origins}))
'''
    database = json.loads(output('docker','compose','exec','-T','api','python','-c',check))
    assert after['counts']['students'] == 60 and after['counts']['academic_snapshots'] == 360
    assert active['inference']['created']+active['inference']['reused']+active['inference']['abstentions'] == active['inference']['selected'] == 60
    assert active['inference']['repeat_created'] == 0 and active['inference']['abstentions'] > 0
    containers = json.loads(output('docker','inspect','riesgo-escolar-api-1','riesgo-escolar-web-1','riesgo-escolar-db-1'))
    assert all(c['State']['Health']['Status'] == 'healthy' for c in containers)
    api = next(c for c in containers if c['Name'] == '/riesgo-escolar-api-1')
    assert any(m.get('Name') == 'riesgo-escolar_ml_data' and m['Destination'] == '/var/lib/riesgo/ml' for m in api['Mounts'])
    old = json.loads(output('docker','inspect','riesgo-escolar-demo-api-1','riesgo-escolar-demo-web-1','riesgo-escolar-demo-db-1'))
    assert all(not c['State']['Running'] for c in old)
    backup = json.loads((ROOT/'tests/evidence/s2-1-backup.json').read_text())
    assert all(hashlib.sha256((Path(backup['backup_private_path'])/n).read_bytes()).hexdigest() == h for n,h in backup['hashes'].items())
    cli = {}
    for command in ('readiness','compatibility','train'):
        result = subprocess.run(['docker','compose','exec','-T','api','python','-m','app.ml.cli',command],
            cwd=ROOT,stdout=subprocess.PIPE,text=True,encoding='utf-8')
        assert result.returncode == (2 if command == 'train' else 0)
        cli[command] = {'exit_code':result.returncode,'response':json.loads(result.stdout)}
    assert not cli['readiness']['response']['ready'] and cli['train']['response']['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    report = {'status':'COMPROBADO','initial_sha':INITIAL,'final_sha':output('git','rev-parse','HEAD'),
        'registered_routes':routes,'active_responses_validated':len(active['cases']),'positive_samples_validated':len(samples),
        'backend_tests':sum(int(s.attrib['tests']) for s in suites),'preserved_files':preserved,
        'users_password_hashes_preserved':True,'historical_environment_stopped':True,'backup_hashes_match':True,
        'prior_sessions_and_audit_preserved':True,
        'database':database,'api_image':api['Image'],'pip_check':output('docker','compose','exec','-T','api','python','-m','pip','check'),
        'cli':cli,'inference':active['inference'],'browser_cases':{scope:len(value['cases']) for scope,value in browser.items()},
        'lock_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('backend/requirements.txt','backend/requirements-dev.txt','package-lock.json')}}
    (ROOT/'tests/evidence/s3-1-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'tests/evidence/s3-1-comparison.json').write_text(json.dumps(active['comparison'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPROBADO: contrato/API, origen sintético, locks/cuentas/historia, CLI REAL bloqueada y persistencia.')


if __name__ == '__main__':
    main()
