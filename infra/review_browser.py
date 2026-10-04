"""Acceso activo autorizado S2.2; contraseñas Windows solo en memoria."""
import json
import os
from pathlib import Path
import subprocess
from review_accounts import credentials
from runtime_snapshot import snapshot, school_unchanged

ROOT=Path(__file__).resolve().parents[1]

def main():
    before=snapshot()
    accounts=credentials()
    prefix=os.environ.get('REVIEW_REPORT_PREFIX','s2-2-active')
    if not prefix.replace('-','').isalnum():
        raise SystemExit('Nombre de reporte inválido.')
    environment={**os.environ,'E2E_BASE_URL':'http://localhost:15173','E2E_SCOPE':'active',
        'E2E_ACCOUNTS':json.dumps(accounts),'E2E_EVIDENCE_PREFIX':prefix,
        'E2E_REPORT_FILE':f'tests/evidence/{prefix}-playwright.json'}
    result=subprocess.run(['cmd','/c','npx','playwright','test'],cwd=ROOT,env=environment)
    after=snapshot()
    assert school_unchanged(before,after), 'La revisión alteró datos escolares o archivos.'
    assert before['users']==after['users'], 'La revisión alteró cuentas.'
    print('Registros escolares, archivos y cuentas conservados durante la revisión visual.')
    raise SystemExit(result.returncode)

if __name__=='__main__':
    main()
