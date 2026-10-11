"""Verify retrospective journal and real API after restoration into a new target."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import httpx
from runtime_target import Target
from windows_credentials import read

CODE = """import json,hashlib
from app.core.config import Settings
from app.repositories.retrospective import RetrospectiveStore
s=RetrospectiveStore(Settings().ml_storage_dir)
s.package()
r=s.history()
print(json.dumps({'ids':[v['id'] for v in r],'hashes':{
    v['id']:hashlib.sha256(s.read_bytes(s.run_name(v['id']))).hexdigest() for v in r},
    'signed_records_valid':True,'package_valid':True}))
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-target', type=Path, required=True)
    parser.add_argument('--restored-target', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise RuntimeError('REPORT_ALREADY_EXISTS')
    source = Target.load(args.source_target)
    restored = Target.load(args.restored_target)
    if source.kind != 'ACTIVE' or restored.kind != 'RESTORE' or source.project == restored.project:
        raise RuntimeError('SEPARATE_RESTORED_TARGET_REQUIRED')
    original = source.api_python(CODE)
    recovered = restored.api_python(CODE)
    if original != recovered or len(recovered['ids']) < 3:
        raise RuntimeError('RETROSPECTIVE_JOURNAL_RECOVERY_MISMATCH')
    with httpx.Client(base_url=restored.web_url, timeout=30) as client:
        login = client.post('/api/v1/auth/login', json=read('ADMIN'), headers={'Origin':restored.web_url})
        if login.status_code != 200:
            raise RuntimeError('RESTORED_CURRENT_ADMIN_LOGIN_FAILED')
        token = login.json()['csrf_token']
        response = client.get('/api/v1/retrospective/evaluations/' + recovered['ids'][0])
        data = response.json()
        if (response.status_code != 200 or len(data['predictions']) != 60 or data['metrics']['correct'] != 49
                or data['metrics']['alert_proposals'] != 40 or not data['source_events_verified']):
            raise RuntimeError('RESTORED_RETROSPECTIVE_API_FAILED')
        export = client.get('/api/v1/retrospective/evaluations/' + recovered['ids'][0] + '/report.csv')
        if export.status_code != 200 or len(export.text.strip().splitlines()) != 61:
            raise RuntimeError('RESTORED_RETROSPECTIVE_CSV_FAILED')
        partial = client.post('/api/v1/retrospective/partial-prediction', headers={'X-CSRF-Token':token}, json={
            'term':'B2','values':{'promedio_parcial_0_20':10,'asistencia_parcial_proporcion':.7,'entrega_parcial_proporcion':.5},
            'available_at':{k:'2026-06-30T00:00:00-05:00' for k in ('promedio_parcial_0_20','asistencia_parcial_proporcion','entrega_parcial_proporcion')}})
        if partial.status_code != 200 or partial.json()['notification_sent'] or partial.json()['intervention_performed']:
            raise RuntimeError('RESTORED_FROZEN_MODEL_FAILED')
        client.post('/api/v1/auth/logout', headers={'X-CSRF-Token':token}).raise_for_status()
    report = {'status':'COMPROBADO','executed_at':datetime.now(timezone.utc).isoformat(),
              'source_project':source.project,'restored_project':restored.project,
              'signed_journal_bytes_exact':True,'signed_evaluations':len(recovered['ids']),
              'package_valid':True,'current_admin_login':True,'csv_rows':60,
              'metrics':data['metrics'],'frozen_partial_inference':True,'regenerated_or_refitted':False}
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'signed_evaluations':report['signed_evaluations'],'restored_project':restored.project}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit(str(error) if isinstance(error,RuntimeError) else 'RETROSPECTIVE_RECOVERY_CHECK_FAILED') from None
