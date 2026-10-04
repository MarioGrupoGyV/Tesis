"""Cierre S6 con destinos explícitos, respaldo DPAPI y evidencia ejecutada vigente."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from backup_restore import db_snapshot, file_inventory, location, verified_content
from runtime_target import LABEL, ROOT, TABLES, Target, code_identity, digest, docker, private_directory

INITIAL = '2029343f3540f7911cd07f6161c5e241f5696626'
ROLES = ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER')
PROTECTED = tuple(table for table in TABLES if table not in ('user_sessions', 'audit_events'))
EXPECTED = {'students': 60, 'enrollments': 60, 'academic_snapshots': 360, 'predictions': 55,
    'followup_decisions': 55, 'alerts': 51, 'interventions': 2, 'app_users': 4, 'model_versions': 1,
    'synthetic_studies': 1, 'import_batches': 1, 'grade_sections': 2}
MANUALS = ('Manual_Instalacion_Windows', 'Manual_Uso_Final', 'Manual_Respaldo_Restauracion',
    'Diccionario_Base_Datos', 'Mapa_Endpoints', 'Arquitectura_Final', 'Matriz_Trazabilidad_Final',
    'Guion_Presentacion_Tecnica', 'Alcance_y_Limitaciones')
CRITICAL = ('infra/runtime_target.py', 'infra/backup_restore.py', 'infra/windows_dpapi.py',
    'infra/operator_profiles.py', 'infra/windows_credentials.py', 'infra/study.py',
    'infra/review_s6.py', 'infra/test_s6_install.py', 'infra/test_s6_profiles_live.py',
    'infra/test_s6_persistence.py',
    'tests/e2e/s6.spec.ts', 'tests/e2e/s6-reporter.ts', 'tests/e2e/review-reporter.ts', 'playwright.config.ts')


class CheckFailure(RuntimeError):
    pass


class Review:
    def __init__(self):
        self.checks = []
        self.evidence = {}

    def require(self, name, condition):
        self.checks.append({'check': name, 'status': 'COMPROBADO' if condition else 'FALLIDO'})
        if not condition:
            raise CheckFailure(name)

    def read(self, name):
        if not re.fullmatch(r's[0-9][a-z0-9.-]+\.json', name):
            raise CheckFailure('EVIDENCE_NAME_INVALID')
        path = ROOT / 'tests/evidence' / name
        value = json.loads(path.read_text(encoding='utf-8'))
        self.evidence[name] = digest(path)
        return value

    def success(self, name):
        result = self.read(name)
        self.require('REPORT_SUCCESS_' + name, result.get('status') == 'COMPROBADO')
        return result


def same_target(review, label, reported, target):
    keys = ('kind', 'project', 'database', 'target_id', 'web_url', 'api_url', 'ports', 'volumes', 'images')
    review.require(label, all(reported.get(key) == target.data[key] for key in keys))


def normalize(path):
    return re.sub(r'\{[^}]+\}', '{}', path)


def current_hashes(review, name, hashes, required):
    review.require(name + '_COVERAGE', set(required) <= set(hashes))
    review.require(name + '_CURRENT', all((ROOT / path).is_file() and digest(ROOT / path) == value
        for path, value in hashes.items()))


def browser_report(review, prefix, target, *, roles=False):
    report = review.read(prefix + '-playwright.json')
    review.require(prefix + '_BROWSER_PASS', report.get('status') == 'passed' and bool(report.get('cases'))
        and all(case.get('status') == 'passed' for case in report['cases']) and report.get('scope') == target.kind)
    if roles:
        review.require(prefix + '_FOUR_ROLES', len(report['cases']) == 4 and all(
            any(re.search(r'\b' + role + r'\b', case['title']) for case in report['cases']) for role in ROLES))
    if not prefix.endswith('-integrated'):
        review.require(prefix + '_NO_SIMULATED_HTTP', all(case.get(key) is False for case in report['cases']
            for key in ('has_simulated_http_503', 'has_simulated_processing_status_503',
                        'has_simulated_preview_stale_409', 'has_simulated_response_body_loss', 'has_simulated_host_clock')))
    login = review.read(prefix + '-login-statuses.json')
    same_target(review, prefix + '_LOGIN_DESTINATION', login['target'], target)
    review.require(prefix + '_LOGIN_PASS', bool(login['attempts']) and all(
        attempt.get('status') == 200 and attempt.get('code') is None for attempt in login['attempts']))
    if roles:
        review.require(prefix + '_LOGIN_FOUR_ROLES', {item['role'] for item in login['attempts']} == set(ROLES))
    return report


def validate_samples(review, contract, prefix):
    samples = review.read(prefix + '-response-samples.json')
    review.require(prefix + '_RESPONSES_PRESENT', isinstance(samples, list) and bool(samples))
    for sample in samples:
        schema = sample.get('schema')
        review.require(prefix + '_KNOWN_SCHEMA', schema in contract['components']['schemas'])
        try:
            Draft202012Validator({'$ref': '#/components/schemas/' + schema, 'components': contract['components']},
                format_checker=FormatChecker()).validate(sample['body'])
        except Exception:
            raise CheckFailure('CONTRACT_RESPONSE_INVALID_' + prefix + '_' + schema) from None
    return samples


def preserved_review(review, prefix, target):
    environment = review.success(prefix + '-environment.json')
    same_target(review, prefix + '_REVIEW_DESTINATION', environment['target'], target)
    before, after = environment['counts_before'], environment['counts_after']
    review.require(prefix + '_ALL_TABLES', set(before) == set(after) == set(TABLES))
    review.require(prefix + '_BUSINESS_COUNTS', all(before[key] == after[key] == value for key, value in EXPECTED.items()))
    review.require(prefix + '_CONSERVATION', all(environment.get(key) is True for key in (
        'protected_table_fingerprints_preserved', 'private_file_hashes_preserved', 'previous_sessions_audit_rows_preserved')))
    review.require(prefix + '_NO_MUTATIONS', environment.get('human_followup_mutations') is False
        and environment.get('regenerated_or_retrained') is False)
    review.require(prefix + '_ACCESS_DELTAS', all(after[table] >= before[table] for table in ('user_sessions', 'audit_events'))
        and after['user_sessions'] - before['user_sessions'] == environment['new_sessions']
        and after['audit_events'] - before['audit_events'] == environment['new_audit_events'])
    browser_report(review, prefix, target, roles=True)
    return environment


def csv_reports(review, prefix, target):
    for role in ('ADMIN', 'TUTOR', 'DIRECTOR'):
        report = review.success(prefix + '-' + role.lower() + '-csv.json')
        same_target(review, prefix + '_' + role + '_CSV_DESTINATION', report['target'], target)
        review.require(prefix + '_' + role + '_CSV_COMPLETE', report.get('role') == role
            and report.get('rows') == (30 if role == 'TUTOR' else 60) and len(report.get('headers', [])) == 19
            and all(report.get(key) is True for key in ('utf8_bom', 'complete_filtered_scope', 'no_free_notes', 'actual_browser_download_response'))
            and re.fullmatch(r'[0-9a-f]{64}', report.get('sha256', '')) is not None)


def read_only_files(target, directory):
    # Docker helper mounts read-only; no app/database startup, signing or training.
    return file_inventory(target, directory)


def document_checks(review, contract):
    documents = [ROOT / 'docs/manuals' / (name + '.md') for name in MANUALS]
    documents += [ROOT / 'README.md', ROOT / 'docs/manuals/README.md', ROOT / 'docs/planning/Estado_Sprint_6.md']
    for path in documents:
        text = path.read_text(encoding='utf-8')
        review.require('DOCUMENT_CONTENT_' + path.stem, len(text.split()) >= 80 and 'REAL' in text)
        for reference in re.findall(r'(?<!!)\[[^\]]+\]\(([^)\n]+)\)', text):
            reference = reference.strip('<>').split('#', 1)[0]
            if not reference or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', reference):
                continue
            review.require('DOCUMENT_LINK_' + path.stem, (path.parent / reference).resolve().exists())
    dictionary = (ROOT / 'docs/manuals/Diccionario_Base_Datos.md').read_text(encoding='utf-8')
    review.require('DICTIONARY_ALL_EFFECTIVE_TABLES', all(table in dictionary for table in TABLES)
        and '0004_followup' in dictionary)
    mapping = (ROOT / 'docs/manuals/Mapa_Endpoints.md').read_text(encoding='utf-8')
    documented = {(method, normalize(path)) for method, path in re.findall(r'^\| (GET|POST|PATCH) `(/[^`]+)`', mapping, re.M)}
    expected = {(method.upper(), normalize(path)) for path, operations in contract['paths'].items()
        for method in operations if method in ('get', 'post', 'patch')}
    review.require('MANUAL_27_IMPLEMENTED_OPERATIONS', documented == expected)
    for name, concepts in {'Manual_Instalacion_Windows': ('--target', '--operator-profile', 'bootstrap-admin'),
        'Manual_Respaldo_Restauracion': ('DPAPI', 'restore-check', 'riesgo_app'),
        'Arquitectura_Final': ('mermaid', 'riesgo_app', 'SYNTHETIC'),
        'Matriz_Trazabilidad_Final': ('s6-', 'COMPROBADO', 'pendiente'),
        'Alcance_y_Limitaciones': ('hipótesis', 'asesor', 'sintético')}.items():
        text = (ROOT / 'docs/manuals' / (name + '.md')).read_text(encoding='utf-8').casefold()
        review.require('DOCUMENT_MEANING_' + name, all(concept.casefold() in text for concept in concepts))


def run(args, review):
    targets = {name: Target.load(getattr(args, name)) for name in ('active', 'install', 'restore')}
    review.require('DESTINATIONS_DISTINCT', len({target.project for target in targets.values()}) == 3
        and len({target.database for target in targets.values()}) == 3
        and len({volume for target in targets.values() for volume in target.data['volumes'].values()}) == 9)
    for name, target in targets.items():
        review.require('DESTINATION_KIND_' + name, target.kind == name.upper())
        containers = target.assert_resources()
        review.require('THREE_GUARDED_CONTAINERS_' + name, len(containers) == 3)
        volumes = json.loads(docker('volume', 'inspect', *target.data['volumes'].values(), text=True).stdout)
        review.require('THREE_VOLUME_PROJECT_LABELS_' + name, len(volumes) == 3
            and {item['Name'] for item in volumes} == set(target.data['volumes'].values())
            and all((item.get('Labels') or {}).get('com.docker.compose.project') == target.project for item in volumes))
        if name != 'active':
            review.require('THREE_VOLUME_TARGET_OWNER_LABELS_' + name,
                all((item.get('Labels') or {}).get(LABEL) == target.target_id for item in volumes))
        if name == 'active':
            target.assert_identity()
            review.require('ACTIVE_HEALTHY', all(item['State']['Running']
                and item['State'].get('Health', {}).get('Status') == 'healthy' for item in containers))
        else:
            review.require('COPY_STOPPED_AND_IDENTIFIABLE_' + name, all(not item['State']['Running'] for item in containers))
    active, install, restore = (targets[name] for name in ('active', 'install', 'restore'))
    contract = yaml.safe_load((ROOT / 'docs/planning/Contrato_API.yaml').read_text(encoding='utf-8'))
    operations = {(method.upper(), normalize('/api/v1' + path), operation['operationId'])
        for path, methods in contract['paths'].items() for method, operation in methods.items() if method in ('get', 'post', 'patch')}
    review.require('CONTRACT_0_5_0_27', contract['info']['version'] == '0.5.0' and len(operations) == 27)
    routes = active.api_python("import json\nfrom app.main import create_app\nprint(json.dumps([(m.upper(),p,o['operationId']) for p,ops in create_app().openapi()['paths'].items() for m,o in ops.items() if m in ('get','post','patch')]))")
    review.require('ACTUAL_API_MATCHES_CONTRACT', {(method, normalize(path), identifier) for method, path, identifier in routes} == operations)
    baseline = review.read('s6-initial-database.json')
    initial_files = review.read('s6-initial-files.json')
    actual = db_snapshot(active)
    review.require('ACTUAL_15_TABLES_HEAD_0004', actual['tables'] == sorted(TABLES) and actual['alembic'] == ['0004_followup'])
    review.require('ACTIVE_OLD_BUSINESS_UNCHANGED', all(actual['fingerprints'][table] == baseline['fingerprints'][table]
        and actual['counts'][table] == baseline['counts'][table] for table in PROTECTED))
    review.require('ACTIVE_S5_COUNTS', all(actual['counts'][table] == count for table, count in EXPECTED.items()))
    role = next(item for item in actual['roles'] if item['name'] == 'riesgo_app')
    review.require('APP_ROLE_NOT_OWNER_OR_SUPERUSER', role['superuser'] is False and role['createdb'] is False and role['createrole'] is False)
    old = active.api_python("""import json,sys
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
p=json.load(sys.stdin);d=Database(Settings());r={}
with d.engine.connect() as c:
 c.execute(text("SET timezone='UTC'"))
 for table,column in [('user_sessions','created_at'),('audit_events','recorded_at')]:
  q="SELECT md5(coalesce(string_agg(row_to_json(x)::text,'' ORDER BY id),'')) FROM (SELECT * FROM risk_school."+table+' ORDER BY '+column+',id LIMIT :count) x'
  r[table]=c.scalar(text(q),{'count':p[table]})
 print(json.dumps(r))
d.engine.dispose()
""", {table: baseline['counts'][table] for table in ('user_sessions', 'audit_events')})
    review.require('ALL_PRIOR_SESSIONS_AUDIT_ROWS_PRESERVED', all(old[table] == baseline['fingerprints'][table] for table in old))
    cases = active.api_python("""import json
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
d=Database(Settings())
with d.engine.connect() as c:
 print(json.dumps({'closed':c.scalar(text("SELECT count(*) FROM risk_school.alerts WHERE status IN ('RESOLVED','DISMISSED')")),
 'done':c.scalar(text("SELECT count(*) FROM risk_school.interventions WHERE status='DONE'")),
 'cancelled':c.scalar(text("SELECT count(*) FROM risk_school.interventions WHERE status='CANCELLED'")),
 'real_school':c.scalar(text("SELECT count(*) FROM risk_school.students WHERE data_origin='REAL'"))}))
d.engine.dispose()
""")
    review.require('ONE_CLOSED_CASE_TWO_ACTIVITIES_REAL_NOT_LOADED', cases == {'closed': 1, 'done': 1, 'cancelled': 1, 'real_school': 0})
    backup_report = review.success(args.backup_report)
    backup_path = location() / backup_report['backup_file']
    content, manifest = verified_content(backup_path)
    review.require('DPAPI_OWN_BACKUP_INTEGRITY', manifest['id'] == backup_report['backup_id']
        and digest(backup_path) == backup_report['cipher_sha256'] and backup_path.stat().st_size == backup_report['bytes']
        and manifest['database'] == backup_report['database'] and backup_report.get('dpapi_round_trip') is True
        and backup_report.get('writers_resumed') is True)
    del content
    review.require('BACKUP_EXPLICIT_ACTIVE_ORIGIN', all(manifest['source'][key] == active.data[key]
        for key in ('kind', 'project', 'database', 'ports', 'volumes', 'images')) and manifest['origin'] == 'SYNTHETIC')
    review.require('BACKUP_CONSISTENT_WINDOW', set(manifest['window']['services_paused']) == {'web', 'api'}
        and datetime.fromisoformat(manifest['window']['start']) < datetime.fromisoformat(manifest['window']['end']))
    inventory = {key.removeprefix('volumes/'): value for key, value in manifest['inventory'].items() if key.startswith('volumes/')}
    review.require('BACKUP_ALL_PRIVATE_FILES', inventory == initial_files and len(inventory) == backup_report['private_file_count']
        and 'ml_data/.internal-key' in inventory)
    temporary_parent = private_directory(Path(os.environ['LOCALAPPDATA']) / 'SeguimientoEscolar/S6/Checks')
    with tempfile.TemporaryDirectory(prefix='s6-final-check-', dir=temporary_parent) as temporary:
        directory = private_directory(Path(temporary))
        review.require('ACTUAL_ACTIVE_PRIVATE_FILES', read_only_files(active, directory) == initial_files)
        review.require('ACTUAL_STOPPED_RESTORE_PRIVATE_FILES', read_only_files(restore, directory) == inventory)
        install_files = read_only_files(install, directory)
        review.require('ACTUAL_INSTALL_PRIVATE_FILES_EXIST', 'ml_data/.internal-key' in install_files and len(install_files) >= 15)
    integrity = review.success(args.integrity_report)
    review.require('NATIVE_VERIFICATION_SAME_BACKUP', integrity['backup_id'] == manifest['id']
        and integrity.get('inventory_verified') is True and integrity.get('dpapi_decrypted') is True and integrity['database'] == manifest['database'])
    restoration = review.success(args.restore_report)
    review.require('RESTORE_DESTINATION_EQUALS_EXPLICIT_TARGET', restoration['kind'] == restore.kind
        and restoration['project'] == restore.project and restoration['database_name'] == restore.database
        and restoration['target_id'] == restore.target_id and restoration['volumes'] == restore.data['volumes']
        and restoration['ports'] == restore.data['ports'] and restoration['backup_id'] == manifest['id'])
    review.require('BEFORE_LOGIN_ALL_TABLES_SCHEMA_FILES_IDENTICAL', restoration['database'] == manifest['database']
        and restoration.get('before_login_exact_all_tables') is True and restoration.get('before_login_exact_all_files') is True
        and set(restoration['database']['fingerprints']) == set(TABLES)
        and restoration['private_file_count'] == len(inventory))
    review.require('RESTORED_HMAC_AND_MODEL_WITHOUT_GENERATION', restoration['trust'] == {
        'hmac_verified': True, 'model_compatible': True, 'algorithm': 'SVM', 'regenerated': False})
    negative = review.success(args.negative_report)
    expected_negatives = {'native_dpapi_corruption': 'DPAPI_INTEGRITY_OR_IDENTITY_FAILED',
        'missing_original_hmac_key': 'BACKUP_INVENTORY_INCOMPLETE', 'incompatible_real_manifest': 'BACKUP_VERSION_INCOMPATIBLE',
        'altered_real_dump': 'BACKUP_FILE_INTEGRITY_FAILED', 'unregistered_external_copy': 'BACKUP_NOT_REGISTERED_OWN_PACKAGE',
        'existing_destination_collision': 'TARGET_DESCRIPTOR_EXISTS'}
    review.require('SIX_REAL_BACKUP_NEGATIVES', negative['cases'] == expected_negatives
        and negative['backup_id'] == manifest['id'] and negative['original_cipher_sha256'] == digest(backup_path)
        and all(negative.get(key) is True for key in ('native_windows_dpapi', 'derived_from_actual_backup', 'original_backup_unchanged'))
        and negative.get('docker_or_active_writes') is False)
    suites = list(ET.parse(ROOT / 'tests/evidence' / (args.backend_prefix + '.xml')).getroot().iter('testsuite'))
    tests = [case.attrib['name'] for suite in suites for case in suite.iter('testcase')]
    review.require('FULL_BACKEND_269_NO_FAILURE_SKIP', sum(int(suite.attrib['tests']) for suite in suites) >= 269
        and all(int(suite.attrib.get(key, 0)) == 0 for suite in suites for key in ('failures', 'errors', 'skipped')))
    review.require('BACKEND_MEANINGFUL_COVERAGE', all(any(keyword in name for name in tests) for keyword in
        ('concurr', 'rollback', 'csrf', 'group', 'revis', 'temporal', 'permissions', 'origin', '503', 'immutable')))
    backend = review.success(args.backend_prefix + '-environment.json')
    review.require('BACKEND_REAL_LINUX_POSTGRES', backend['platform'] == 'Linux' and backend['python'] == '3.12.12'
        and backend['postgresql'].startswith('17.6') and backend['exit_code'] == 0 and backend['database'].startswith('riesgo_escolar_test_'))
    for filename, total, required in ((args.recovery_report, 29, ('infra/runtime_target.py', 'infra/backup_restore.py', 'infra/windows_dpapi.py')),
                                    ('s6-profiles-native.json', 16, ('infra/operator_profiles.py', 'infra/study.py', 'infra/windows_credentials.py'))):
        report = review.success(filename)
        review.require(filename + '_NATIVE_ALL_PASS', report['runtime']['platform'] == 'Windows' and report['tests'] == report['passed'] == total
            and all(report[key] == 0 for key in ('failures', 'errors', 'skipped')) and all(item['status'] == 'COMPROBADO' for item in report['cases']))
        current_hashes(review, filename, report['executed_code_sha256'], required)
        if filename == args.recovery_report:
            review.require('RECOVERY_NATIVE_WINDOWS_ACTUAL_AND_STORAGE_COMMAND', sum(
                case.get('scope') == 'NATIVE_WINDOWS_DPAPI_AND_PRIVATE_TEMPORARIES' for case in report['cases']) == 4
                and any('test_helpers_override_inherited_application_labels' in case['test'] for case in report['cases'])
                and report['docker_or_active_database_mutated'] is False)
        else:
            review.require('TWO_ACTUAL_NATIVE_CREDENTIAL_MANAGER_CASES', sum(
                case.get('scope') == 'NATIVE_WINDOWS_CREDENTIAL_MANAGER' for case in report['cases']) == 2)
    install_environment = review.success(args.install_prefix + '-environment.json')
    same_target(review, 'INSTALL_TARGET_MATCH', install_environment['target'], install)
    review.require('INSTALL_TRUE_EMPTY_NO_COPY', set(install_environment['clean_counts']) == set(TABLES)
        and all(count == 0 for count in install_environment['clean_counts'].values()) and install_environment['clean_tables'] == 15
        and install_environment['copied_database_or_artifacts'] is False and install_environment['automatic_bootstrap'] is False
        and install_environment['database_role'] == 'riesgo_app' and install_environment['target_stopped_and_preserved'] is True)
    review.require('INSTALL_EXPLICIT_REPRODUCIBLE_UI_FLOW', all(install_environment.get(key) is True for key in
        ('bootstrap_repeated_rejected', 'reproducible_generation_reused', 'first_import_via_real_browser_api',
         'first_inference_via_real_browser_api', 'explicit_cli_comparison_registration_activation', 'period_lock_real_api_ui'))
        and install_environment['seed'] == 1729 and install_environment['generation_version'] == 'synthetic-generator-v1'
        and install_environment['integrated_roles'] == list(ROLES))
    initial_inference = install_environment['initial_inference']
    review.require('INSTALL_FIRST_INFERENCE_NOT_PRECREATED', initial_inference['created'] == 55 and initial_inference['reused'] == 0
        and initial_inference['followup']['created'] == 51 and install_environment['abstentions'] == 5
        and all(install_environment['counts_after'][table] == value for table, value in EXPECTED.items()))
    profiles = install_environment['explicit_admin_profile_check']
    review.require('OWN_ADMIN_REAL_NATIVE_PROFILE_AND_REJECTIONS', profiles['status'] == 'COMPROBADO'
        and profiles['http_login_attempts'] == 4 and {item['case'] for item in profiles['cases']} == {'own_admin_valid_12_to_19', 'invalid', 'non_admin', 'inactive'}
        and all(item['status'] == 'COMPROBADO' for item in profiles['cases']) and all(profiles.get(key) is True for key in
            ('temporary_profiles_cleaned', 's22_entries_unchanged', 'admin_active_restored')) and profiles['secret_files_created'] is False)
    review.require('PROFILE_LIVE_CODE_CURRENT', profiles['executed_code_sha256']['test_s6_profiles_live.py'] == digest(ROOT / 'infra/test_s6_profiles_live.py'))
    browser_report(review, args.install_prefix + '-import', install)
    browser_report(review, args.install_prefix + '-integrated', install, roles=True)
    browser_report(review, args.install_prefix + '-period-lock', install)
    environments = {'install': preserved_review(review, args.install_prefix + '-review', install),
        'restore': preserved_review(review, args.restore_prefix, restore), 'active': preserved_review(review, args.active_prefix, active)}
    for prefix, target in ((args.install_prefix + '-review', install), (args.restore_prefix, restore)):
        outage = review.success(prefix + '-outage-infrastructure-failure.json')
        same_target(review, prefix + '_REAL_OUTAGE_DESTINATION', outage['target'], target)
        review.require(prefix + '_REAL_POSTGRES_STOP_RECOVERY', all(outage.get(key) is True for key in
            ('real_postgresql_stop', 'web_and_api_kept_running', 'sanitized_error', 'ui_no_false_success', 'real_database_recovery'))
            and outage['http_mock'] is False and outage['health_503_schema'] == 'Health' and outage['database_operation_503_schema'] == 'Error')
        browser_report(review, prefix + '-outage', target)
        samples = validate_samples(review, contract, prefix + '-outage')
        review.require(prefix + '_ACTUAL_503_TYPES', any(sample['schema'] == 'Health' and sample['body']['status'] == 'unavailable' for sample in samples)
            and any(sample['schema'] == 'Error' and sample['body']['code'] == 'SERVICE_UNAVAILABLE' for sample in samples))
    review.require('ACTIVE_NO_INFRASTRUCTURE_FAILURE', environments['active']['real_postgresql_outage'] is False)
    all_samples = []
    for prefix in (args.backend_prefix, args.backend_prefix + '-ml', args.backend_prefix + '-followup'):
        all_samples.extend(validate_samples(review, contract, prefix))
    for prefix, target in ((args.install_prefix + '-import', install), (args.install_prefix + '-integrated', install),
        (args.install_prefix + '-period-lock', install), (args.install_prefix + '-review', install),
        (args.restore_prefix, restore), (args.active_prefix, active)):
        samples = validate_samples(review, contract, prefix)
        all_samples.extend(samples)
        if prefix in (args.install_prefix + '-review', args.restore_prefix, args.active_prefix):
            csv_reports(review, prefix, target)
            predictions = [sample['body'] for sample in samples if sample['schema'] == 'PredictionRunResult']
            followup = [sample['body'] for sample in samples if sample['schema'] == 'FollowupResult']
            review.require(prefix + '_ACTUAL_REUSED_INFERENCE_SYNC', bool(predictions) and bool(followup)
                and all(item['created'] == 0 and item['reused'] == 55 and item['followup']['created'] == 0
                    and item['followup']['reused'] == 55 for item in predictions)
                and all(item['created'] == 0 and item['updated'] == 0 and item['reused'] == 55 for item in followup))
            summaries = [sample['body'] for sample in samples if sample['schema'] == 'ReportSummary' and sample['body']['total'] == 60]
            review.require(prefix + '_S5_CLOSED_ACTIVITY_COUNTS', bool(summaries) and all(item['cases']['resolved'] == 1
                and item['interventions']['done'] == 1 and item['interventions']['cancelled'] == 1 for item in summaries))
    review.require('CURRENT_CONTRACT_COVERAGE', {'ImportBatch', 'ImportCommit', 'StudentPage', 'StudentDetail',
        'TimelineEventPage', 'ProcessingStatus', 'PredictionRunResult', 'FollowupResult', 'AlertPage', 'AlertDetail',
        'InterventionCreateResult', 'InterventionView', 'ReportSummary', 'Error'} <= {sample['schema'] for sample in all_samples})
    persistence = review.success(args.restore_prefix + '-persistence.json')
    review.require('RESTORE_ALL_15_TABLES_FILES_PERSISTENCE', persistence['kind'] == restore.kind and persistence['project'] == restore.project
        and persistence['database'] == restore.database and persistence['counts_before'] == persistence['counts_after']
        and set(persistence['counts_before']) == set(TABLES) and all(persistence.get(key) is True for key in
            ('all_15_tables_alembic_schema_roles_exact', 'all_private_files_exact', 'stopped_and_preserved'))
        and persistence['active_database_restarted'] is False and persistence['private_file_count'] == len(inventory))
    identity = code_identity()
    review.require('HEAD_NO_S6_COMMIT', identity['head'] == INITIAL)
    review.require('BACKUP_LOCKS_CURRENT', manifest['code']['locks'] == identity['locks'])
    tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', INITIAL], cwd=ROOT, text=True).splitlines()
    preserved = [name for name in tracked if name.startswith(('backend/app/ml/', 'backend/migrations/', 'tests/evidence/', 'docs/adr/'))
        or re.search(r'docs/planning/(Estado_Sprint_|Matriz_verificacion_)', name)
        or name.endswith(('requirements.in', 'requirements.txt', 'requirements-dev.in', 'requirements-dev.txt', 'requirements-s0.in', 'requirements-s0.txt'))
        or name in ('package.json', 'package-lock.json', 'frontend/package.json')]
    for name in preserved:
        original = subprocess.check_output(['git', 'show', INITIAL + ':' + name], cwd=ROOT)
        current = (ROOT / name).read_bytes()
        if Path(name).suffix.lower() not in ('.png', '.jpg', '.pdf', '.jpeg'):
            original, current = original.replace(b'\r\n', b'\n'), current.replace(b'\r\n', b'\n')
        review.require('PRESERVE_' + name, original == current)
    build = review.success('s6-build-checks.json')
    required_code = {*CRITICAL, *(str(path.relative_to(ROOT)).replace('\\', '/') for directory in ('backend/app', 'frontend/src')
        for path in (ROOT / directory).rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'))}
    current_hashes(review, 'FINAL_BUILD_EXECUTED_CODE', build['executed_code_sha256'], required_code)
    review.require('FINAL_BUILD_IMAGES_MATCH_TARGETS', all(build['images'] == target.data['images'] for target in targets.values()))
    checks = build['checks']
    commands = [' '.join(check['command']) if isinstance(check['command'], list) else check['command'] for check in checks]
    review.require('FINAL_BUILD_ALL_COMMANDS_SUCCESS', bool(checks) and all(check.get('exit_code') == 0 for check in checks))
    review.require('FINAL_BUILD_COMMAND_COVERAGE', any('generate:api' in command for command in commands)
        and any('npm' in command and 'build' in command for command in commands)
        and any('docker' in command and 'build' in command for command in commands)
        and any('pip check' in command for command in commands) and any('git diff --check' in command for command in commands))
    review.require('FINAL_BUILD_HOST_IMAGE_DISTRIBUTION_EQUAL', build.get('frontend_host_image_assets_identical') is True
        and bool(build.get('frontend_host_dist')) and build['frontend_host_dist'] == build.get('frontend_image_dist'))
    pip = subprocess.check_output(active.command('exec', '-T', 'api', 'python', '-m', 'pip', 'check'), cwd=ROOT, text=True).strip()
    review.require('ACTUAL_ACTIVE_PIP_CHECK', pip == 'No broken requirements found.')
    visual = review.success('s6-browser-visual-review.json')
    images = visual['final_images']
    review.require('VISUAL_ACTUAL_INSPECTIONS', bool(images) and all(image.get('inspected') is True and image.get('findings') for image in images))
    sizes = set()
    for image in images:
        path = ROOT / image['file']
        review.require('FINAL_VISUAL_PREFIX_AND_HASH', path.parent == ROOT / 'tests/evidence' and path.name.startswith(
            (args.install_prefix, args.restore_prefix, args.active_prefix)) and digest(path) == image['sha256'])
        header = path.read_bytes()[:24]
        review.require('REAL_PNG_DIMENSIONS', header[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', header[16:24]) == (image['width'], image['height']))
        viewport = image.get('viewport', {})
        sizes.add((viewport.get('width'), viewport.get('height')))
    review.require('VISUAL_THREE_REQUESTED_VIEWPORTS', {(1440, 900), (768, 1024), (390, 844)} <= sizes)
    image_names = ' '.join(image['file'] for image in images)
    review.require('VISUAL_CRITICAL_STATES', all(name in image_names for name in ('history', 'case', 'reports', 'outage')))
    old_environment = json.loads(docker('inspect', 'riesgo-escolar-demo-api-1', 'riesgo-escolar-demo-web-1', 'riesgo-escolar-demo-db-1', text=True).stdout)
    review.require('HISTORICAL_DEMO_STOPPED', len(old_environment) == 3 and all(not item['State']['Running'] for item in old_environment))
    historical = review.read('s2-1-backup.json')
    review.require('HISTORICAL_BACKUP_INTACT', all(digest(Path(historical['backup_private_path']) / name) == value for name, value in historical['hashes'].items()))
    document_checks(review, contract)
    return {'status': 'COMPROBADO', 'initial_sha': INITIAL, 'final_head': identity['head'],
        'checked_at': datetime.now(UTC).isoformat(), 'code_tree_sha256': identity['tree_sha256'],
        'executed_code_sha256': {name: digest(ROOT / name) for name in (*CRITICAL, 'infra/check_s6.py')},
        'locks': identity['locks'], 'targets': {name: target.data for name, target in targets.items()},
        'backend_tests': len(tests), 'profiles_native_tests': 16, 'recovery_tests': 29,
        'validated_contract_responses': len(all_samples), 'api_operations': len(operations),
        'backup': {'id': manifest['id'], 'file': backup_path.name, 'cipher_sha256': digest(backup_path),
            'private_file_count': len(inventory), 'native_dpapi_verified': True},
        'counts_active': actual['counts'], 'actual_active_and_stopped_restore_files_verified': True,
        'copy_databases': 'Before-login restoration fingerprints, protected real API/UI reviews and exact persistence; copies stay stopped during this checker.',
        'checks': review.checks, 'evidence_sha256': review.evidence,
        'limits': ['Simulación local SYNTHETIC, REAL bloqueado', 'Sin eficacia escolar, hipótesis ni aceptación académica',
            'Sin certificado de accesibilidad o auditoría integral de seguridad', 'Sin commit, push o despliegue externo']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('active', 'install', 'restore', 'report'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--install-prefix', default='s6-install-verified')
    parser.add_argument('--restore-prefix', default='s6-restored-final')
    parser.add_argument('--active-prefix', default='s6-active-final')
    parser.add_argument('--backend-prefix', default='s6-backend-final')
    parser.add_argument('--backup-report', default='s6-backup-final-code.json')
    parser.add_argument('--integrity-report', default='s6-backup-final-code-integrity.json')
    parser.add_argument('--restore-report', default='s6-restore-final-code.json')
    parser.add_argument('--negative-report', default='s6-backup-negative-final.json')
    parser.add_argument('--recovery-report', default='s6-recovery-tests-final-code.json')
    args = parser.parse_args(argv)
    if args.report.exists() or args.report.absolute().parent != ROOT / 'tests/evidence':
        parser.error('Informe nuevo en tests/evidence; no se sobrescribe evidencia')
    review = Review()
    try:
        result = run(args, review)
        status = 0
    except Exception as error:
        result = {'status': 'FALLIDO', 'check': str(error) if isinstance(error, CheckFailure) else 'S6_VERIFICATION_EXCEPTION',
            'error_type': type(error).__name__, 'checked_at': datetime.now(UTC).isoformat(),
            'checks': review.checks, 'evidence_sha256': review.evidence}
        if isinstance(error, RuntimeError) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,100}', str(error)):
            result['error_code'] = str(error)
        status = 2
    with args.report.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({'status': result['status'], 'checks': len(review.checks), 'check': result.get('check')}))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
