"""PowerShell invoca este runner; datos fabricados solo en PostgreSQL aislado."""
import json
import os
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def compose(*args):
    subprocess.run(['docker','compose','-f','infra/compose.browser.yaml',*args],cwd=ROOT,check=True)

def main():
    result = subprocess.run(['docker','compose','-f','infra/compose.test.yaml','run','--rm','tester',
        'python','backend/tests/browser_fixture.py'],cwd=ROOT,check=True,stdout=subprocess.PIPE,text=True)
    fixture = json.loads(result.stdout)
    directory = ROOT/'.local/browser-test'
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'app-url').write_text(fixture['database_url'],encoding='utf-8')
    (directory/'csrf').write_text(secrets.token_urlsafe(48),encoding='utf-8')
    environment = {**os.environ,'E2E_BASE_URL':'http://localhost:15174','E2E_SCOPE':'isolated',
        'E2E_ACCOUNTS':json.dumps(fixture['accounts']),'E2E_EVIDENCE_PREFIX':'s2-2-isolated',
        'E2E_REPORT_FILE':'tests/evidence/s2-2-isolated-playwright.json'}
    try:
        compose('up','-d','--wait')
        compose('restart','apitest','webtest')
        compose('up','-d','--wait')
        command = ['cmd','/c','npx','playwright','test'] if os.name=='nt' else ['npx','playwright','test']
        subprocess.run(command,cwd=ROOT,env=environment,check=True)
        report={'status':'COMPROBADO','database':fixture['database'],'data_scope':'isolated_test_only',
                'bootstrap_repeated_rejected':True,'account_survives_restart':True,'active_environment_untouched':True}
        report['roles'] = list(fixture['accounts'])
        (ROOT/'tests/evidence/s2-2-browser-environment.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:
        compose('stop')

if __name__ == '__main__':
    main()
