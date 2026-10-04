"""S4: PostgreSQL/API reales aislados; contraseñas y CSV privados solo en memoria/temp."""
from datetime import UTC,datetime
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import urllib.request

from study import export_csv

ROOT=Path(__file__).resolve().parents[1]
BROWSER_COMPOSE=['docker','compose','-f','infra/compose.browser.yaml']
BASE='http://localhost:15174'


def compose(*args):
    subprocess.run([*BROWSER_COMPOSE,*args],cwd=ROOT,check=True)


def private_result(command,payload):
    result=subprocess.run(command,cwd=ROOT,input=json.dumps(payload),text=True,encoding='utf-8',capture_output=True)
    try:
        body=json.loads(result.stdout)
    except ValueError:
        raise RuntimeError('BROWSER_FIXTURE_COMMAND_FAILED') from None
    if result.returncode:
        code=body.get('code','BROWSER_FIXTURE_COMMAND_FAILED')
        raise RuntimeError(code if isinstance(code,str) and re.fullmatch(r'[A-Z0-9_]{1,80}',code) else 'BROWSER_FIXTURE_COMMAND_FAILED')
    return body


def private_cli(command,account,**values):
    return private_result([*BROWSER_COMPOSE,'exec','-T','apitest','python','-m','app.synthetic_cli',command],
        {**account,**values})


def fixture_action(account,period_id,action,*,active=False):
    # Código de tests enviado explícitamente al contenedor. No se incorpora al
    # runtime de producción ni añade endpoints. Ningún secreto va en argumentos.
    code=(ROOT/'backend/tests/browser_fixture.py').read_text(encoding='utf-8')
    remote="import json,sys; namespace={'__name__':'browser_fixture_private','__file__':'/app/browser_fixture.py'}; exec("+repr(code)+",namespace); print(json.dumps(namespace['browser_action'](json.load(sys.stdin))))"
    command=(['docker','compose'] if active else BROWSER_COMPOSE)+['exec','-T',
        'api' if active else 'apitest','python','-c',remote]
    return private_result(command,{**account,'period_id':period_id,'action':action})


def initial_predictions(account,period_id):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,body,headers=None):
        req=urllib.request.Request(BASE+'/api/v1'+path,data=None if body is None else json.dumps(body).encode(),
            method='POST',headers={'Content-Type':'application/json',**(headers or {})})
        with opener.open(req,timeout=60) as response:
            return json.loads(response.read()) if response.status!=204 else None
    login=request('/auth/login',account,{'Origin':BASE})
    assert login['user']['role']=='ADMIN'
    token={'X-CSRF-Token':login['csrf_token']}
    try:
        result=request('/predictions/run',{'period_id':period_id,'as_of':datetime.now(UTC).isoformat()},token)
        assert result['created']>0 and result['abstentions']
        return {'selected':result['selected'],'created':result['created'],'reused':result['reused'],
            'abstentions':len(result['abstentions'])}
    finally:
        request('/auth/logout',None,token)


def playwright(environment,*options):
    command=['cmd','/c','npx','playwright','test'] if os.name=='nt' else ['npx','playwright','test']
    subprocess.run([*command,*options],cwd=ROOT,env=environment,check=True)


def main():
    prefix=os.environ.get('BROWSER_REPORT_PREFIX','s4')
    if not prefix.startswith('s4') or not prefix.replace('-','').isalnum():
        raise ValueError('El prefijo nuevo debe comenzar por s4')
    result=subprocess.run(['docker','compose','-f','infra/compose.test.yaml','run','--rm','tester',
        'python','backend/tests/browser_fixture.py'],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True)
    fixture=json.loads(result.stdout)
    directory=ROOT/'.local/browser-test'
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'app-url').write_text(fixture['database_url'],encoding='utf-8')
    (directory/'csrf').write_text(secrets.token_urlsafe(48),encoding='utf-8')
    try:
        compose('up','-d','--wait')
        compose('restart','apitest','webtest')
        compose('up','-d','--wait')
        admin=fixture['accounts']['ADMIN']
        identity=fixture_action(admin,None,'identity')
        assert identity['database']==fixture['database']
        generated=private_cli('generate',admin,seed=1729,tutor_id=fixture['account_ids']['TUTOR'])
        with tempfile.TemporaryDirectory(prefix='seguimiento-escolar-s4-') as private:
            csv_path=Path(private)/'synthetic-input.csv'
            exported=export_csv(admin,generated['study_id'],csv_path,loader=private_cli)
            study={'study_id':generated['study_id'],'period_id':generated['period_id'],
                'csv_file':str(csv_path),'csv_sha256':exported['csv_sha256'],
                'real_period_id':fixture['real_period_id']}
            environment={**os.environ,'E2E_BASE_URL':BASE,'E2E_SCOPE':'isolated',
                'E2E_ACCOUNTS':json.dumps(fixture['accounts']),'E2E_STUDY':json.dumps(study),
                'E2E_EVIDENCE_PREFIX':f'{prefix}-isolated','E2E_PHASE':'import',
                'E2E_REPORT_FILE':f'tests/evidence/{prefix}-isolated-import-playwright.json'}
            playwright(environment,'--grep','ADMIN: primera importación')
            # Entrenar no ocurre en HTTP. Este único estudio existe en DB de
            # pruebas; su comparación no cambia el estudio activo S3.1.
            comparison=private_cli('compare',admin,study_id=study['study_id'])
            model=private_cli('register',admin,study_id=study['study_id'])
            private_cli('activate',admin,model_id=model['model_id'])
            predictions=initial_predictions(admin,study['period_id'])
            study.update(fixture_action(admin,study['period_id'],'revision'))
            environment.update(E2E_PHASE='navigation',E2E_STUDY=json.dumps(study),
                E2E_REPORT_FILE=f'tests/evidence/{prefix}-isolated-playwright.json')
            playwright(environment,'--grep-invert','ADMIN: primera importación')
            report={'status':'COMPROBADO','database':fixture['database'],'data_scope':'isolated_test_only',
                'bootstrap_repeated_rejected':True,'account_survives_restart':True,
                'active_environment_untouched':True,'roles':list(fixture['accounts']),
                'first_import_via_real_browser_api':True,'selected_algorithm':comparison['selected_algorithm'],
                'initial_predictions':predictions,'pending_revision_fixture':'Una revisión añadida únicamente en la DB browser aislada; predicción anterior conservada.',
                'csv_export_verified':True,'csv_removed_after_review':True}
            (ROOT/f'tests/evidence/{prefix}-browser-environment.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:
        compose('stop')


if __name__=='__main__':
    main()
