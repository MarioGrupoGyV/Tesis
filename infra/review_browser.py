"""S4 activo: exportación/reutilización explícita; cuentas Windows solo en memoria."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import UUID
from review_accounts import credentials
from runtime_snapshot import snapshot, school_unchanged
from study import export_csv
from test_browser import fixture_action

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description='Revisar S4 sobre el estudio existente sin regenerar ni reentrenar.')
    parser.add_argument('--study-id',required=True,type=UUID)
    parser.add_argument('--period-id',required=True,type=UUID)
    args=parser.parse_args()
    before=snapshot()
    accounts=credentials()
    prefix=os.environ.get('REVIEW_REPORT_PREFIX','s4-active')
    if not prefix.startswith('s4') or not prefix.replace('-','').isalnum():
        raise SystemExit('El prefijo nuevo debe comenzar por s4.')
    returncode=2
    exported_ok=False
    try:
        with tempfile.TemporaryDirectory(prefix='seguimiento-escolar-s4-active-') as private:
            csv_path=Path(private)/'synthetic-input.csv'
            exported=export_csv(accounts['ADMIN'],str(args.study_id),csv_path)
            exported_ok=True
            if exported['period_id']!=str(args.period_id):
                raise RuntimeError('STUDY_CONTEXT_MISMATCH')
            study=fixture_action(accounts['ADMIN'],str(args.period_id),'describe',active=True)
            study.update(study_id=str(args.study_id),csv_file=str(csv_path),csv_sha256=exported['csv_sha256'])
            environment={**os.environ,'E2E_BASE_URL':'http://localhost:15173','E2E_SCOPE':'active',
                'E2E_ACCOUNTS':json.dumps(accounts),'E2E_STUDY':json.dumps(study),
                'E2E_EVIDENCE_PREFIX':prefix,'E2E_PHASE':'navigation',
                'E2E_REPORT_FILE':f'tests/evidence/{prefix}-playwright.json'}
            command=['cmd','/c','npx','playwright','test'] if os.name=='nt' else ['npx','playwright','test']
            result=subprocess.run([*command,'--grep-invert','ADMIN: primera importación'],cwd=ROOT,env=environment)
            returncode=result.returncode
    finally:
        after=snapshot()
        preserved=school_unchanged(before,after) and before['users']==after['users']
        report={'status':'COMPROBADO' if returncode==0 and preserved else 'FALLIDO',
            'scope':'active_existing_synthetic_study','school_and_private_files_unchanged':preserved,
            'users_preserved':before['users']==after['users'],'counts_before':before['counts'],
            'counts_after':after['counts'],'regenerated_or_retrained':False,
            'csv_export_verified':exported_ok,'csv_removed_after_review':True}
        (ROOT/f'tests/evidence/{prefix}-environment.json').write_text(json.dumps(report,indent=2)+'\n')
        assert preserved, 'La revisión alteró datos escolares, archivos o cuentas.'
    print('Revisión S4: registros, archivos privados y cuentas conservados; CSV temporal retirado.')
    raise SystemExit(returncode)

if __name__=='__main__':
    main()
