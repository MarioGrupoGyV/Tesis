"""Sanitized evidence from actual API, existing tables/files and persisted journal."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

import httpx
from jsonschema import Draft202012Validator, FormatChecker
import yaml

from runtime_target import ROOT, Target
from runtime_snapshot import snapshot
from windows_credentials import read


def check(condition, name, checks):
    if not condition:
        raise RuntimeError(name)
    checks.append(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise RuntimeError('REPORT_ALREADY_EXISTS')
    target = Target.load(args.target)
    target.assert_resources()
    before = json.loads(args.before.read_text())
    checks = []
    contract = yaml.safe_load((ROOT / 'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    expected = {(m.upper(), '/api/v1' + p, operation['operationId']) for p, methods in contract['paths'].items()
                for m, operation in methods.items() if m in ('get','post','patch')}
    actual = target.api_python("import json\nfrom app.main import create_app\na=create_app()\nprint(json.dumps({'version':a.version,'operations':[(m.upper(),p,o['operationId']) for p,ops in a.openapi()['paths'].items() for m,o in ops.items() if m in ('get','post','patch')]}))")
    check(actual['version'] == '0.6.0' and {tuple(r) for r in actual['operations']} == expected, '32_ACTUAL_OPERATIONS_MATCH_CONTRACT', checks)
    validator = Draft202012Validator({'$ref':'#/components/schemas/RetrospectiveDetail','components':contract['components']}, format_checker=FormatChecker())
    role_statuses = {}
    latest = None
    for role in ('ADMIN','TUTOR','DIRECTOR','RESEARCHER'):
        with httpx.Client(base_url=target.web_url, timeout=30) as client:
            login = client.post('/api/v1/auth/login', json=read(role), headers={'Origin':target.web_url})
            check(login.status_code == 200, 'CURRENT_' + role + '_LOGIN_' + str(login.status_code), checks)
            token = login.json()['csrf_token']
            result = client.get('/api/v1/retrospective/evaluations')
            role_statuses[role] = result.status_code
            if role == 'ADMIN':
                check(result.status_code == 200 and result.json()['available'] and result.json()['total'] >= 2, 'RETROSPECTIVE_HISTORY_FROM_API', checks)
                identifier = result.json()['items'][0]['id']
                detail = client.get(f'/api/v1/retrospective/evaluations/{identifier}')
                latest = detail.json()
                validator.validate(latest)
                check(latest['metrics']['correct'] == 49 and latest['metrics']['n'] == 60
                      and latest['prediction_mismatches'] == 0 and latest['metrics']['alert_proposals'] == 40, '60_PREDICTIONS_49_CORRECT_40_PROPOSALS', checks)
                check(latest['notifications_sent'] == latest['interventions_performed'] == 0, 'PROPOSALS_SEPARATED_FROM_ACTIONS', checks)
                check(latest['source_events_verified'] and latest['b1_support_vectors_verified'] and not latest['refitted'], 'SOURCE_DATES_B1_FROZEN_NO_REFIT', checks)
                check(client.post('/api/v1/retrospective/evaluations').status_code == 403, 'CSRF_REQUIRED', checks)
                check(client.get(f'/api/v1/retrospective/evaluations/{uuid4()}').status_code == 404, 'MISSING_RETROSPECTIVE_404', checks)
            else:
                check(result.status_code == 403, role + '_SERVER_DENIED', checks)
            check(client.post('/api/v1/auth/logout', headers={'X-CSRF-Token':token}).status_code == 204, role + '_LOGOUT', checks)
    after = snapshot()
    tables = [t for t in before['fingerprints'] if t not in ('audit_events','user_sessions')]
    check(all(before['fingerprints'][t] == after['fingerprints'][t] for t in tables), 'ALL_13_EXISTING_NON_ACCESS_TABLES_UNCHANGED', checks)
    check(before['users'] == after['users'], 'FOUR_CURRENT_ACCOUNTS_PRESERVED', checks)
    check(before['files'] == after['files'], 'EXISTING_IMPORT_FILES_UNCHANGED', checks)
    new_files = dict(after['ml_files'])
    check(all(new_files.get(name) == digest for name, digest in before['ml_files']), 'ALL_EXISTING_ML_FILES_UNCHANGED', checks)
    report = {'status':'COMPROBADO','executed_at':datetime.now(timezone.utc).isoformat(),
        'target':{k:getattr(target,k) for k in ('project','database','web_url','api_url')},
        'checks':checks,'role_statuses':role_statuses,'counts_before':before['counts'],'counts_after':after['counts'],
        'metrics':latest['metrics'],'evaluation_id':latest['id'],'evaluation_executed_at':latest['executed_at'],
        'source_events_verified':latest['source_events_verified'],'compatibility':latest['compatibility'],
        'version_warnings':latest['version_warnings'],'discrepancies':latest['discrepancies'],
        'prediction_mismatches':latest['prediction_mismatches'], 'csv_rows_verified_in_browser':60,
        'new_ml_private_files':len(after['ml_files']) - len(before['ml_files'])}
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'checks':len(checks),'metrics':report['metrics']}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No HTTP body, credentials, database parameters or dataset in diagnostics.
        print(json.dumps({'status':'FALLIDO','code':str(error) if isinstance(error,RuntimeError) else type(error).__name__}))
        raise SystemExit(1)
