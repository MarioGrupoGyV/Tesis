"""Revisión activa S5 explícita: casos/actividades simuladas autorizadas, sin ML nuevo."""
import argparse
import json
import os
import subprocess
from uuid import UUID

from review_accounts import credentials
from runtime_snapshot import snapshot,SCHOOL
from test_browser import ROOT,fixture_action


def main():
    parser=argparse.ArgumentParser(description='Revisión S5 del estudio activo, con mínimo seguimiento sintético conservado.')
    parser.add_argument('--study-id',required=True,type=UUID)
    parser.add_argument('--period-id',required=True,type=UUID)
    args=parser.parse_args()
    prefix=os.environ.get('REVIEW_REPORT_PREFIX','s5-active')
    if not prefix.startswith('s5') or not prefix.replace('-','').isalnum():
        raise SystemExit('El prefijo nuevo debe comenzar por s5.')
    target=ROOT/f'tests/evidence/{prefix}-environment.json'
    if target.exists():
        raise SystemExit('Usa un prefijo nuevo para conservar la evidencia S5 anterior.')
    before=snapshot();accounts=credentials();returncode=2
    try:
        study=fixture_action(accounts['ADMIN'],str(args.period_id),'describe',active=True)
        study.update(study_id=str(args.study_id),scope='active')
        environment={**os.environ,'E2E_BASE_URL':'http://localhost:15173','E2E_SCOPE':'active',
            'E2E_ACCOUNTS':json.dumps(accounts),'E2E_STUDY':json.dumps(study),
            'E2E_EVIDENCE_PREFIX':prefix,'E2E_PHASE':'followup',
            'E2E_REPORT_FILE':f'tests/evidence/{prefix}-playwright.json'}
        command=['cmd','/c','npx','playwright','test'] if os.name=='nt' else ['npx','playwright','test']
        result=subprocess.run([*command,'--grep','^S5'],cwd=ROOT,env=environment)
        returncode=result.returncode
    finally:
        after=snapshot()
        protected=[table for table in SCHOOL if table not in ('alerts','interventions','followup_decisions')]
        preserved=all(before['fingerprints'].get(t)==after['fingerprints'].get(t) for t in protected)
        preserved=preserved and before['files']==after['files'] and before['ml_files']==after['ml_files']
        users=before['users']==after['users'] and before['fingerprints']['app_users']==after['fingerprints']['app_users']
        report={'status':'COMPROBADO' if returncode==0 and preserved and users else 'FALLIDO',
            'scope':'active_registered_synthetic_study','academic_model_predictions_and_private_files_preserved':preserved,
            'users_preserved':users,'counts_before':before['counts'],'counts_after':after['counts'],
            'regenerated_or_retrained':False,'followup_is_simulation':True,
            'human_workflow_policy':'Dos actividades simuladas (DONE/CANCELLED) y un caso concluido; repeticiones verifican recursos ya registrados.'}
        target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        assert preserved and users,'Se alteró evidencia escolar/ML anterior o cuentas.'
    raise SystemExit(returncode)


if __name__=='__main__':
    main()
