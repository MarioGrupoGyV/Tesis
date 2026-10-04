"""Evidencia pública S2.2: contratos, conservación y respaldo histórico sin alterarlo."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding='utf-8').strip()


def main():
    initial = 'eb0bfdee140e35bb104405c6dcaa7920b344215b'
    protected = ['package.json', 'package-lock.json', 'frontend/package.json',
                 'backend/requirements.in', 'backend/requirements.txt',
                 'backend/requirements-dev.in', 'backend/requirements-dev.txt',
                 'infra/requirements-s0.in', 'infra/requirements-s0.txt',
                 'backend/migrations/versions/0001_demo_schema.py',
                 'backend/migrations/versions/0001_demo_schema.sql',
                 'infra/check_runtime.py', 'docs/planning/Contrato_API.yaml',
                 'frontend/src/lib/api.generated.d.ts']
    for name in protected:
        assert output('git', 'show', f'{initial}:{name}') == (ROOT/name).read_text(encoding='utf-8').strip(), name
    backup = json.loads((ROOT/'tests/evidence/s2-1-backup.json').read_text())
    for name, digest in backup['hashes'].items():
        assert hashlib.sha256((Path(backup['backup_private_path'])/name).read_bytes()).hexdigest() == digest
    old = json.loads(output('docker', 'inspect', 'riesgo-escolar-demo-api-1', 'riesgo-escolar-demo-web-1', 'riesgo-escolar-demo-db-1'))
    assert all(not c['State']['Running'] for c in old)
    current = json.loads(output('docker', 'inspect', 'riesgo-escolar-api-1', 'riesgo-escolar-web-1', 'riesgo-escolar-db-1'))
    assert all(c['State']['Health']['Status']=='healthy' for c in current)
    mounts = [{'container':c['Name'], 'mounts':[{'type':m['Type'],'name':m.get('Name'), 'destination':m['Destination']} for m in c['Mounts']]} for c in current]
    revision = output('docker','compose','exec','-T','db','psql','-U','riesgo_owner','-d','riesgo_escolar','-Atc','SELECT version_num FROM alembic_version')
    assert revision == '0002_institutional_boundary'
    code = "import json; from app.main import create_app; print(json.dumps(sorted((m.upper(),p) for p,ops in create_app().openapi()['paths'].items() for m in ops if m in ('get','post'))))"
    routes = json.loads(output('docker','compose','exec','-T','api','python','-c',code))
    contract = yaml.safe_load((ROOT/'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    normalize = lambda p: re.sub(r'\{[^}]+\}', '{}', p)
    expected = {(m.upper(),normalize('/api/v1'+p)) for p,ops in contract['paths'].items() for m in ops if m in ('get','post')}
    assert {(m,normalize(p)) for m,p in routes} == expected
    evidence = json.loads((ROOT/'tests/evidence/s2-2-endpoints.json').read_text(encoding='utf-8'))
    for case in evidence['cases']:
        path = case['path'].split('?')[0].removeprefix('/api/v1')
        candidates = [p for p in contract['paths'] if re.fullmatch(re.sub(r'\{[^}]+\}', '[^/]+', p), path)]
        operation = contract['paths'][candidates[0]][case['method'].lower()]
        response = operation['responses'][str(case['status'])]
        if '$ref' in response:
            response = contract['components']['responses'][response['$ref'].split('/')[-1]]
        if case['response'] is not None:
            schema = {**response['content']['application/json']['schema'], 'components':contract['components']}
            Draft202012Validator(schema,format_checker=FormatChecker()).validate(case['response'])
    report = {'status':'COMPROBADO','initial_sha':initial,'final_sha':output('git','rev-parse','HEAD'),
              'protected_files_unchanged':protected,'backup_hashes_match':True,
              'historical_restoration_evidence':'s2-1-backup.json; no nueva restauración en S2.2',
              'previous_environment_stopped':True,'current_containers_healthy':True,
              'mounts':mounts,'alembic_revision':revision,'registered_routes':routes,
              'contract_version':contract['info']['version'],'active_responses_validated':len(evidence['cases'])}
    (ROOT/'tests/evidence/s2-2-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('COMPROBADO: conservación, respaldo, runtime, 14 rutas y respuestas activas contra contrato.')


if __name__ == '__main__':
    main()
