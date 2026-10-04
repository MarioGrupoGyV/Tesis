"""Contrato S3, conservación de dependencias/datos y diagnóstico operativo sanitizado."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from runtime_snapshot import snapshot, ROOT, SCHOOL

INITIAL='0c6063f65cfe84dd5d122439cc8ee899527da617'


def output(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True,encoding='utf-8').strip()


def pins(content):
    return dict(re.findall(r'^([\w.-]+)==([^\s;\\]+)',content,re.M))


def main():
    contract=yaml.safe_load((ROOT/'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    assert contract['info']['version']=='0.3.0' and len(contract['paths'])==18
    code="import json; from app.main import create_app; print(json.dumps(sorted((m.upper(),p) for p,ops in create_app().openapi()['paths'].items() for m in ops if m in ('get','post'))))"
    routes=json.loads(output('docker','compose','exec','-T','api','python','-c',code))
    normalize=lambda p:re.sub(r'\{[^}]+\}','{}',p)
    assert {(m,normalize(p)) for m,p in routes}=={(m.upper(),normalize('/api/v1'+p)) for p,ops in contract['paths'].items() for m in ops if m in ('get','post')}
    samples=json.loads((ROOT/'tests/evidence/s3-ml-response-samples.json').read_text())
    for sample in samples:
        Draft202012Validator({'$ref':'#/components/schemas/'+sample['schema'],'components':contract['components']},format_checker=FormatChecker()).validate(sample['body'])
    active=json.loads((ROOT/'tests/evidence/s3-active-endpoints.json').read_text(encoding='utf-8'))
    for case in active['cases']:
        path=case['path'].split('?')[0].removeprefix('/api/v1')
        key=path if path in contract['paths'] else next(p for p,ops in contract['paths'].items()
            if case['method'].lower() in ops and re.fullmatch(re.sub(r'\{[^}]+\}','[^/]+',p),path))
        response=contract['paths'][key][case['method'].lower()]['responses'][str(case['status'])]
        if case['response'] is not None:
            schema={**response['content']['application/json']['schema'],'components':contract['components']}
            Draft202012Validator(schema,format_checker=FormatChecker()).validate(case['response'])
    preserved=['package.json','package-lock.json','frontend/package.json','infra/check_runtime.py',
        'infra/requirements-s0.in','infra/requirements-s0.txt','backend/migrations/versions/0001_demo_schema.py',
        'backend/migrations/versions/0001_demo_schema.sql','backend/migrations/versions/0002_institutional_boundary.py',
        'frontend/src/app/App.tsx','tests/e2e/access.spec.ts','infra/windows_credentials.py']
    for file in preserved:
        assert output('git','show',INITIAL+':'+file)==(ROOT/file).read_text(encoding='utf-8').strip(),file
    for file in ('backend/requirements.txt','backend/requirements-dev.txt'):
        old=pins(output('git','show',INITIAL+':'+file)); new=pins((ROOT/file).read_text())
        assert all(new[k]==v for k,v in old.items()) and set(new)-set(old)=={'xgboost-cpu'}
        assert new['xgboost-cpu']=='3.4.1'
    before=json.loads((ROOT/'.local/s3-before.json').read_text(encoding='utf-8'))
    after=snapshot()
    assert all(before['fingerprints'][t]==after['fingerprints'][t] for t in SCHOOL)
    assert before['fingerprints']['app_users']==after['fingerprints']['app_users']
    assert before['files']==after['files'] and before['ml_files']==after['ml_files']
    assert after['counts']['model_versions']==after['counts']['predictions']==0
    containers=json.loads(output('docker','inspect','riesgo-escolar-api-1','riesgo-escolar-web-1','riesgo-escolar-db-1'))
    assert all(c['State']['Health']['Status']=='healthy' for c in containers)
    api=next(c for c in containers if c['Name']=='/riesgo-escolar-api-1')
    assert any(m.get('Name')=='riesgo-escolar_ml_data' and m['Destination']=='/var/lib/riesgo/ml' for m in api['Mounts'])
    old=json.loads(output('docker','inspect','riesgo-escolar-demo-api-1','riesgo-escolar-demo-web-1','riesgo-escolar-demo-db-1'))
    assert all(not c['State']['Running'] for c in old)
    backup=json.loads((ROOT/'tests/evidence/s2-1-backup.json').read_text())
    assert all(hashlib.sha256((Path(backup['backup_private_path'])/n).read_bytes()).hexdigest()==h for n,h in backup['hashes'].items())
    cli={}
    for command in ('readiness','configuration','compatibility','train'):
        result=subprocess.run(['docker','compose','exec','-T','api','python','-m','app.ml.cli',command],
                              cwd=ROOT,stdout=subprocess.PIPE,text=True,encoding='utf-8')
        assert result.returncode==(2 if command=='train' else 0)
        cli[command]={'exit_code':result.returncode,'response':json.loads(result.stdout)}
    assert not cli['readiness']['response']['ready'] and cli['train']['response']['code']=='INSTITUTIONAL_PROCESSING_NOT_READY'
    pip=output('docker','compose','exec','-T','api','python','-m','pip','check')
    report={'status':'COMPROBADO','initial_sha':INITIAL,'final_sha':output('git','rev-parse','HEAD'),
        'registered_routes':routes,'active_responses_validated':len(active['cases']),'positive_samples_validated':len(samples),
        'preserved_files':preserved,'only_new_distribution':'xgboost-cpu==3.4.1',
        'school_counts':{t:after['counts'][t] for t in SCHOOL},'users_unchanged':True,
        'private_imports_and_ml_unchanged':True,'historical_environment_stopped':True,'backup_hashes_match':True,
        'api_image':api['Image'],'pip_check':pip,'cli':cli,
        'lock_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ('backend/requirements.txt','backend/requirements-dev.txt')}}
    (ROOT/'tests/evidence/s3-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('COMPROBADO: 18 rutas, contrato, conservación, dependencias CPU y bloqueo CLI.')


if __name__=='__main__':
    main()
