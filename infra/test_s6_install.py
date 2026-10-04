"""Instalación S6 nueva y recorrido UI real; destino y preparación explícitos."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
from uuid import uuid4

from review_s6 import describe, playwright, public_target, review, snapshot, validate_prefix
from runtime_target import ROOT, TABLES, Target
from study import export_csv


PREPARE_ACCOUNTS = '''
import json,sys
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
from app.bootstrap_admin import AdministratorInput,BootstrapError,create_first_admin
from app.configure_context import UserInput,PeriodInput,configure
from app.models.s1 import AppUser
payload=json.load(sys.stdin)
database=Database(Settings())
with database.session_factory() as db:
 assert db.scalar(text('SELECT count(*) FROM risk_school.app_users'))==0
 values=AdministratorInput(**payload['accounts']['ADMIN'],display_name='Administrador propio de prueba S6 aislada')
 administrator_id=create_first_admin(db,values)
 try:
  create_first_admin(db,values)
  raise AssertionError('BOOTSTRAP_REPETITION_NOT_REJECTED')
 except BootstrapError:
  pass
 administrator=db.get(AppUser,administrator_id)
 identifiers={'ADMIN':str(administrator_id)}
 for role in ('TUTOR','DIRECTOR','RESEARCHER'):
  identifiers[role]=str(configure(db,administrator,UserInput(**payload['accounts'][role],display_name='Cuenta temporal aislada S6 '+role,role=role)))
 real_period=str(configure(db,administrator,PeriodInput(code=payload['real_period_code'],school_year=2026,start_date='2026-01-01',end_date='2026-12-31')))
print(json.dumps({'account_ids':identifiers,'real_period_id':real_period,'bootstrap_repeated_rejected':True}))
database.engine.dispose()
'''


def create_accounts(target):
    if target.kind != 'INSTALL':
        raise RuntimeError('S6_ACCOUNT_PREPARATION_ONLY_NEW_INSTALLATION')
    identifier = uuid4().hex[:12]
    # Exclusivos del test y memoria del launcher. No defaults ni almacén Windows.
    accounts = {role: {'email': f's6-{identifier}-{role.lower()}@example.com', 'password': secrets.token_urlsafe(24)}
                for role in ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER')}
    accounts['ADMIN']['password'] = secrets.token_urlsafe(12)  # 16 caracteres válidos; no política fixture de 20.
    prepared = target.api_python(PREPARE_ACCOUNTS, {'accounts': accounts, 'real_period_code': 'S6-EMPTY-' + identifier})
    return accounts, prepared


def wait_login_window(started):
    # Conserva el límite vigente; separa lotes de autenticación completos en vez
    # de relajar controles, reiniciar API o reintentar intentos rechazados.
    remaining = max(0, 301 - (time.monotonic() - started))
    waited = remaining
    while remaining > 0:
        print('S6: esperando la ventana de acceso existente antes del siguiente lote de revisión.', flush=True)
        time.sleep(min(30, remaining))
        remaining = max(0, 301 - (time.monotonic() - started))
    return round(waited, 2)


def run(target, prefix, *, stop=True):
    validate_prefix(prefix)
    if target.kind != 'INSTALL':
        raise RuntimeError('S6_INSTALLATION_NEW_TARGET_REQUIRED')
    target.assert_identity()
    empty = snapshot(target)
    if sorted(empty['counts']) != sorted(TABLES) or any(empty['counts'].values()):
        raise RuntimeError('S6_INSTALLATION_NOT_EMPTY')
    began = datetime.now(UTC).isoformat()
    report = {'status': 'FALLIDO', 'target': public_target(target), 'started_at': began,
              'clean_counts': empty['counts'], 'clean_tables': 15, 'database_role': 'riesgo_app',
              'copied_database_or_artifacts': False, 'automatic_bootstrap': False,
              'bootstrap_scope': 'Cuentas aleatorias temporales preparadas explícitamente por servicios reales en el destino aislado; no entrada manual.',
              'institutional_processing': False}
    try:
        accounts, prepared = create_accounts(target)
        from test_s6_profiles_live import check_live
        login_window = time.monotonic()
        profile_result = check_live(target, accounts)
        assert profile_result['status'] == 'COMPROBADO'
        report['explicit_admin_profile_check'] = profile_result
        report['bootstrap_repeated_rejected'] = prepared['bootstrap_repeated_rejected']
        def loader(command, account, **values):
            return target.api_command('app.synthetic_cli', command, {**account, **values})
        generated = loader('generate', accounts['ADMIN'], seed=1729, tutor_id=prepared['account_ids']['TUTOR'])
        repeated = loader('generate', accounts['ADMIN'], seed=1729, tutor_id=prepared['account_ids']['TUTOR'])
        assert repeated['reused'] and repeated['study_id'] == generated['study_id']
        assert repeated['csv_sha256'] == generated['csv_sha256']
        report.update(study_id=generated['study_id'], period_id=generated['period_id'],
                      generation_version=generated['manifest']['generator_version'], seed=1729,
                      csv_sha256=generated['csv_sha256'], reproducible_generation_reused=True)
        prepared_counts = snapshot(target)['counts']
        assert all(prepared_counts[name] == 0 for name in ('students', 'enrollments', 'academic_snapshots', 'predictions', 'model_versions', 'alerts', 'interventions', 'followup_decisions'))
        with tempfile.TemporaryDirectory(prefix='seguimiento-escolar-s6-install-') as private:
            csv = Path(private) / 'registered-synthetic.csv'
            exported = export_csv(accounts['ADMIN'], generated['study_id'], csv, loader=loader)
            assert exported['csv_sha256'] == generated['csv_sha256']
            study = {'study_id': generated['study_id'], 'period_id': generated['period_id'],
                     'csv_file': str(csv), 'csv_sha256': generated['csv_sha256'], 'real_period_id': prepared['real_period_id']}
            import_prefix = prefix + '-import'; validate_prefix(import_prefix)
            playwright(target, accounts, study, import_prefix, 's6-import')
            after_import = snapshot(target)['counts']
            assert after_import['students'] == 60 and after_import['academic_snapshots'] == 360
            assert after_import['predictions'] == 0 and after_import['alerts'] == 0
            report['first_import_via_real_browser_api'] = True
            comparison = loader('compare', accounts['ADMIN'], study_id=study['study_id'])
            model = loader('register', accounts['ADMIN'], study_id=study['study_id'])
            assert model['algorithm'] == comparison['selected_algorithm']
            activated = loader('activate', accounts['ADMIN'], model_id=model['model_id'])
            assert activated['is_active'] and activated['approval_kind'] == 'TECHNICAL_SIMULATION'
            report.update(selected_algorithm=comparison['selected_algorithm'],
                          explicit_cli_comparison_registration_activation=True)
            study.update(describe(target, accounts['ADMIN'], study['study_id'], study['period_id']))
            report['login_wait_before_integrated_seconds'] = wait_login_window(login_window)
            login_window = time.monotonic()
            integrated_prefix = prefix + '-integrated'; validate_prefix(integrated_prefix)
            playwright(target, accounts, study, integrated_prefix, 's6-integrated')
            samples = json.loads((ROOT / f'tests/evidence/{integrated_prefix}-response-samples.json').read_text(encoding='utf-8'))
            first = next(item['body'] for item in samples if item['schema'] == 'PredictionRunResult' and item['body']['created'] > 0)
            assert first['created'] == 55 and first['reused'] == 0 and len(first['abstentions']) == 5
            assert first['followup']['created'] == 51
            after = snapshot(target)['counts']
            assert after['students'] == 60 and after['academic_snapshots'] == 360 and after['predictions'] == 55
            assert after['followup_decisions'] == 55 and after['alerts'] == 51 and after['interventions'] == 2
            blocked_prefix = prefix + '-period-lock'; validate_prefix(blocked_prefix)
            playwright(target, accounts, study, blocked_prefix, 's6-period-lock')
            # Una revisión posterior reutiliza todo el estado; no vuelve a crear
            # actividades. Provoca una caída real solo en este destino nuevo.
            report['login_wait_before_review_seconds'] = wait_login_window(login_window)
            final_review = review(target, prefix + '-review', study['study_id'], study['period_id'], accounts=accounts, outage=True)
            assert final_review['status'] == 'COMPROBADO'
            report.update(status='COMPROBADO', study_id=study['study_id'], period_id=study['period_id'],
                          selected_algorithm=comparison['selected_algorithm'], generation_version=generated['manifest'].get('generator_version'),
                          csv_sha256=exported['csv_sha256'], reproducible_generation_reused=True,
                          first_import_via_real_browser_api=True, first_inference_via_real_browser_api=True,
                          initial_inference={key: first[key] for key in ('selected', 'created', 'reused', 'followup')},
                          abstentions=5, explicit_cli_comparison_registration_activation=True,
                          integrated_roles=['ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'], counts_after=after,
                          period_lock_real_api_ui=True,
                          review_evidence_prefix=prefix + '-review', csv_removed_after_review=True)
    finally:
        report['finished_at'] = datetime.now(UTC).isoformat()
        try:
            report['counts_at_finish'] = snapshot(target)['counts']
        except (RuntimeError, OSError, ValueError):
            report['counts_at_finish_unavailable'] = True
        try:
            if stop:
                target.compose('stop')
                report['target_stopped_and_preserved'] = True
        finally:
            (ROOT / f'tests/evidence/{prefix}-environment.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--prefix', required=True)
    args = parser.parse_args(argv)
    try:
        result = run(Target.load(args.target), args.prefix)
        print(json.dumps({'status': result['status'], 'target': result['target'], 'study_id': result['study_id'], 'period_id': result['period_id']}))
    except (RuntimeError, ValueError, OSError, AssertionError, subprocess.CalledProcessError) as error:
        code = str(error) if isinstance(error, RuntimeError) and re.fullmatch(r'[A-Z0-9_]{1,100}', str(error)) else 'S6_INSTALLATION_REVIEW_FAILED'
        print(json.dumps({'code': code})); return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
