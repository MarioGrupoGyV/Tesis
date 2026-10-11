"""Actual app inference and guarded API/web restart; preserve DB and private journal."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import httpx

from backup_restore import db_snapshot, file_inventory
from runtime_snapshot import snapshot
from runtime_target import Target, write_new, private_directory
from windows_credentials import read

REFERENCE = {'python': '3.12.14', 'scikit_learn': '1.8.0', 'numpy': '2.3.5',
             'scipy': '1.17.0', 'joblib': '1.5.3', 'threadpoolctl': '3.6.0'}


def verify_result(result):
    assert result['compatibility'] == 'COMPATIBLE_REFERENCE_RUNTIME'
    assert result['versions'] == REFERENCE and result['version_warnings'] == []
    metrics = result['metrics']
    assert metrics['n'] == 60 and metrics['correct'] == 49
    assert abs(metrics['accuracy'] - 49 / 60) < 1e-12
    assert abs(metrics['f1_macro'] - .7930479204842023) < 1e-12
    assert metrics['alert_proposals'] == 40
    assert result['refitted'] is False and result['scaler_b1_verified'] and result['b1_support_vectors_verified']
    assert result['notifications_sent'] == result['interventions_performed'] == 0
    assert len(result['predictions']) == 60 and result['prediction_mismatches'] == 0 and not result['discrepancies']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    if args.report.exists():
        raise RuntimeError('NEW_REPORT_REQUIRED')
    target = Target.load(args.target)
    assert target.kind == 'ACTIVE'
    target.assert_resources()
    before = json.loads(args.before.read_text())
    checks = []
    probe = target.api_python("import json,platform,sklearn,numpy,scipy,joblib\nfrom app.ml.retrospective_runtime import invoke\nprint(json.dumps({'reference':invoke('probe'),'backend':{'python':platform.python_version(),'scikit_learn':sklearn.__version__,'numpy':numpy.__version__,'scipy':scipy.__version__,'joblib':joblib.__version__}}))")
    assert probe['reference']['versions'] == REFERENCE and probe['reference']['isolated']
    checks.append('EXACT_REFERENCE_RUNTIME_SEPARATE_FROM_BACKEND')
    if args.restart:
        db_started = next(c['State']['StartedAt'] for c in target.containers() if c['Config']['Labels']['com.docker.compose.service'] == 'db')
        with tempfile.TemporaryDirectory(prefix='svm-restart-', dir=target.path.parent) as directory:
            private_directory(directory)
            database_before = db_snapshot(target)
            files_before = file_inventory(target, Path(directory))
            target.compose('restart', 'api', 'web', capture_output=True)
            target.compose('up', '-d', '--no-deps', '--wait', 'api', 'web', capture_output=True)
            assert db_snapshot(target) == database_before
            assert file_inventory(target, Path(directory)) == files_before
        assert db_started == next(c['State']['StartedAt'] for c in target.containers() if c['Config']['Labels']['com.docker.compose.service'] == 'db')
        checks.extend(['API_WEB_RESTARTED_DB_NOT_RESTARTED', 'ALL_15_TABLES_EXACT_AFTER_RESTART', 'ALL_PRIVATE_FILES_EXACT_AFTER_RESTART'])
    with httpx.Client(base_url=target.web_url, timeout=45) as client:
        login = client.post('/api/v1/auth/login', json=read('ADMIN'), headers={'Origin': target.web_url})
        assert login.status_code == 200
        token = login.json()['csrf_token']
        history = client.get('/api/v1/retrospective/evaluations').json()
        assert history['total'] >= 4
        verify_result(client.get('/api/v1/retrospective/evaluations/' + history['items'][0]['id']).json())
        old = [r for r in history['items'] if r['compatibility'] == 'CROSS_VERSION_EXPERIMENTAL']
        assert len(old) == 3 and all(len(r['version_warnings']) == 3 for r in old)
        checks.append('THREE_HISTORICAL_INCOMPATIBLE_RUNS_WARNINGS_PRESERVED')
        response = client.post('/api/v1/retrospective/evaluations', headers={'X-CSRF-Token': token})
        assert response.status_code == 200
        result = response.json()
        verify_result(result)
        checks.append('FULL_60_B2_INFERENCE_AFTER_RESTART' if args.restart else 'FULL_60_B2_INFERENCE')
        csv = client.get('/api/v1/retrospective/evaluations/' + result['id'] + '/report.csv')
        assert csv.status_code == 200 and len(csv.text.strip().splitlines()) == 61
        checks.append('ACTUAL_CSV_60_ROWS')
        partial = client.post('/api/v1/retrospective/partial-prediction', headers={'X-CSRF-Token': token}, json={
            'term': 'B2', 'values': {'promedio_parcial_0_20': 10, 'asistencia_parcial_proporcion': .7, 'entrega_parcial_proporcion': .5},
            'available_at': {key: '2026-06-30T00:00:00-05:00' for key in ('promedio_parcial_0_20', 'asistencia_parcial_proporcion', 'entrega_parcial_proporcion')}})
        assert partial.status_code == 200 and partial.json()['versions'] == REFERENCE
        assert partial.json()['compatibility'] == 'COMPATIBLE_REFERENCE_RUNTIME' and partial.json()['version_warnings'] == []
        checks.append('PARTIAL_INFERENCE_REFERENCE_RUNTIME')
        assert client.post('/api/v1/auth/logout', headers={'X-CSRF-Token': token}).status_code == 204
    journal = target.api_python("import json\nfrom app.repositories.retrospective import RetrospectiveStore\nfrom app.core.config import Settings\ns=RetrospectiveStore(Settings().ml_storage_dir)\nr=s.history()[0]\nprint(json.dumps({k:r[k] for k in ('model_sha256','package_sha256','runtime_lock_sha256','runtime_id')}))")
    assert journal['model_sha256'] == '69efc39488faec44b25fd151d638659b4bcc7189d644e0cd96ccec2667137c15'
    assert journal['runtime_lock_sha256'] == hashlib.sha256((Path(__file__).resolve().parents[1] / 'backend/requirements-retrospective.txt').read_bytes()).hexdigest()
    checks.append('ORIGINAL_MODEL_HASH_AND_REFERENCE_LOCK_IN_SIGNED_RUN')
    after = snapshot()
    tables = [table for table in before['fingerprints'] if table not in ('audit_events', 'user_sessions')]
    assert all(before['fingerprints'][table] == after['fingerprints'][table] for table in tables)
    assert before['users'] == after['users'] and before['files'] == after['files']
    current = dict(after['ml_files'])
    assert all(current.get(name) == digest for name, digest in before['ml_files'])
    checks.extend(['ALL_13_EXISTING_NON_ACCESS_TABLES_UNCHANGED', 'FOUR_CURRENT_ACCOUNTS_UNCHANGED', 'ALL_PREEXISTING_PRIVATE_BYTES_UNCHANGED'])
    report = {'status': 'COMPROBADO', 'executed_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'target_project': target.project, 'images': target.data['images'], 'backend_versions': probe['backend'],
        'reference_runtime': probe['reference'], 'latest_evaluation_id': result['id'], 'latest_executed_at': result['executed_at'],
        'metrics': result['metrics'], 'compatibility': result['compatibility'], 'version_warnings': result['version_warnings'],
        'journal_identity': journal, 'counts_before': before['counts'], 'counts_after': after['counts'],
        'historical_incompatible_runs_preserved': len(old), 'new_evaluations': len(after['ml_files']) - len(before['ml_files']),
        'restart_completed': args.restart}
    write_new(args.report, (json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'status': report['status'], 'checks': len(checks), 'metrics': result['metrics'], 'compatibility': result['compatibility']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'FALLIDO', 'code': str(error) if isinstance(error, RuntimeError) else type(error).__name__}))
        raise SystemExit(1)
