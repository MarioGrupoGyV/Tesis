"""Recorrido S5 exclusivo sobre API/PostgreSQL/artefactos de prueba aislados."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

from study import export_csv
from test_browser import ROOT,BASE,compose,private_cli,fixture_action,playwright


def main():
    prefix=os.environ.get('BROWSER_REPORT_PREFIX','s5-isolated')
    if not prefix.startswith('s5') or not prefix.replace('-','').isalnum():
        raise ValueError('El prefijo nuevo debe comenzar por s5')
    target=ROOT/f'tests/evidence/{prefix}-environment.json'
    if target.exists():
        raise ValueError('Usa un prefijo nuevo para conservar la evidencia S5 anterior')
    result=subprocess.run(['docker','compose','-f','infra/compose.test.yaml','run','--rm','tester',
        'python','backend/tests/browser_fixture.py'],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True)
    fixture=json.loads(result.stdout)
    directory=ROOT/'.local/browser-test';directory.mkdir(parents=True,exist_ok=True)
    (directory/'app-url').write_text(fixture['database_url'],encoding='utf-8')
    (directory/'csrf').write_text(secrets.token_urlsafe(48),encoding='utf-8')
    report={'status':'FALLIDO','scope':'isolated_test_only','database':fixture['database'],
        'database_role':'riesgo_app','roles':list(fixture['accounts']),
        'active_environment_untouched':True,'csv_removed_after_review':True}
    try:
        compose('up','-d','--wait');compose('restart','apitest','webtest');compose('up','-d','--wait')
        admin=fixture['accounts']['ADMIN']
        identity=fixture_action(admin,None,'identity');assert identity['database']==fixture['database']
        generated=private_cli('generate',admin,seed=1729,tutor_id=fixture['account_ids']['TUTOR'])
        with tempfile.TemporaryDirectory(prefix='seguimiento-escolar-s5-isolated-') as private:
            path=Path(private)/'synthetic-input.csv'
            exported=export_csv(admin,generated['study_id'],path,loader=private_cli)
            study={'study_id':generated['study_id'],'period_id':generated['period_id'],
                'csv_file':str(path),'csv_sha256':exported['csv_sha256'],'real_period_id':fixture['real_period_id']}
            env={**os.environ,'E2E_BASE_URL':BASE,'E2E_SCOPE':'isolated',
                'E2E_ACCOUNTS':json.dumps(fixture['accounts']),'E2E_STUDY':json.dumps(study),
                'E2E_EVIDENCE_PREFIX':prefix,'E2E_PHASE':'import',
                'E2E_REPORT_FILE':f'tests/evidence/{prefix}-import-playwright.json'}
            playwright(env,'--grep','ADMIN: primera importación')
            comparison=private_cli('compare',admin,study_id=study['study_id'])
            model=private_cli('register',admin,study_id=study['study_id'])
            private_cli('activate',admin,model_id=model['model_id'])
            # Describe no inserta predicciones. La primera evaluación y su
            # seguimiento se ejecutan desde el botón real del navegador S5.
            study.update(fixture_action(admin,study['period_id'],'describe'))
            env.update(E2E_PHASE='followup',E2E_STUDY=json.dumps(study),
                E2E_REPORT_FILE=f'tests/evidence/{prefix}-playwright.json')
            playwright(env,'--grep','^S5')
            samples=json.loads((ROOT/f'tests/evidence/{prefix}-response-samples.json').read_text(encoding='utf-8'))
            initial=next(item['body'] for item in samples
                if item['schema']=='PredictionRunResult' and item['body']['created']>0)
            assert initial['created']==55 and initial['reused']==0 and len(initial['abstentions'])==5
            report['initial_inference']={key:initial[key] for key in ('selected','created','reused','followup')}
            report['initial_inference']['abstentions']=len(initial['abstentions'])
            report.update(status='COMPROBADO',selected_algorithm=comparison['selected_algorithm'],
                first_import_via_real_browser_api=True,complete_followup_via_real_browser_api=True,
                first_inference_via_real_browser_api=True,
                csv_export_verified=True,training_scope='only_isolated_fixture')
    finally:
        compose('stop')
        target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
