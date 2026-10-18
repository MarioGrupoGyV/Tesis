"""Orquestador de la corrida REAL local (Bloque 5): carga los CSV convertidos en un destino AISLADO y ejecuta, dentro del sistema, la
comparación de modelos, la activación, la evaluación retrospectiva y los indicadores. Reanudable e idempotente.

    py -3.12 infra/run_real_study.py --target <destino.json> --operator-profile <perfil> --input <carpeta de cortes.csv/cierres.csv>
                                     --results <carpeta de resultados FUERA de Git> [--dry-run] [--confirm-protocol]
                                     [--tutor-a <uuid>] [--tutor-b <uuid>] [--public-summary <archivo agregado>]
                                     [--confirm-active riesgo-escolar --pre-backup <respaldo .sebackup>]   (solo destino ACTIVE)

Pasos (cada uno reconoce su estado y no duplica): periodo → secciones → protocolo (confirmar solo con --confirm-protocol) → estudio institucional →
importación (verificación de hash) → cierres (el backend calcula RIESGO_V1) → comprobaciones → comparación → registro y activación del modelo →
evaluación retrospectiva de cada bimestre → indicadores y verificación SQL independiente. Imprime solo conteos y códigos de estado: nunca filas,
códigos de alumno ni nombres. Todo lo que tiene filas por alumno va a `--results` (fuera de Git).
Destino ACTIVE (la instalación de siempre): solo con --confirm-active <proyecto> y --pre-backup (respaldo S6 verificado de ese proyecto, en 0008 y de
menos de 24 h); allí nunca se elige solo al único tutor existente (hay que indicar --tutor-a/--tutor-b o --locked-tutor). Con --dry-run no se exige.
La contraseña del ADMIN sale del perfil Windows existente, jamás de argumentos.
"""
import argparse
import base64
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_real_excel as converter  # noqa: E402  (inside_git_tree y sha256)
import load_closings  # noqa: E402

LIMA = ZoneInfo('America/Lima')
PERIOD_CODE = 'REAL-{year}'
SECTION_GRADE = 3
PARTICIPATION_LABELS = {'1': 'Nunca', '2': 'Rara vez', '3': 'A veces', '4': 'Frecuentemente', '5': 'Siempre'}
LEVELS = ('LOW', 'MEDIUM', 'HIGH')
ES = {'LOW': 'Bajo', 'MEDIUM': 'Medio', 'HIGH': 'Alto'}
MODEL_NAMES = {'DUMMY': 'Dummy', 'RANDOM_FOREST': 'Random Forest', 'SVM': 'SVM', 'XGBOOST': 'XGBoost'}
PRE_BACKUP_HEAD = '0008_real_chain'
PRE_BACKUP_MAX_AGE_HOURS = 24


class StopRun(Exception):
    """Detención controlada con código estable (sin valores de los archivos)."""

    def __init__(self, code, detail=None, exit_code=2):
        super().__init__(code)
        self.code, self.detail, self.exit_code = code, detail, exit_code


def key(*parts):
    return str(uuid5(NAMESPACE_URL, 'real-study:' + ':'.join(parts)))


# ---------------------------------------------------------------- entradas
class Inputs:
    """cortes.csv + cierres.csv + resumen_conversion.json: hashes verificados y calendario derivado (solo agregados en memoria)."""

    def __init__(self, folder):
        folder = Path(folder)
        if converter.inside_git_tree(folder):
            raise StopRun('INPUT_INSIDE_GIT')
        self.cortes_path, self.cierres_path = folder / 'cortes.csv', folder / 'cierres.csv'
        summary_path = folder / 'resumen_conversion.json'
        for path in (self.cortes_path, self.cierres_path, summary_path):
            if not path.is_file():
                raise StopRun('INPUT_FILE_MISSING', path.name)
        self.summary = json.loads(summary_path.read_text(encoding='utf-8'))
        self.cortes = self.cortes_path.read_bytes()
        self.cierres = self.cierres_path.read_bytes()
        for name, content in (('cortes.csv', self.cortes), ('cierres.csv', self.cierres)):
            if hashlib.sha256(content).hexdigest() != self.summary.get('outputs', {}).get(name, {}).get('sha256'):
                raise StopRun('INPUT_HASH_MISMATCH', name)
        self.cut_rows = list(csv.DictReader(io.StringIO(self.cortes.decode('utf-8'))))
        self.close_rows = list(csv.DictReader(io.StringIO(self.cierres.decode('utf-8'))))
        self.codes = sorted({row['student_code'] for row in self.cut_rows})
        self.calendar = self._calendar()
        self.year = min(item['start'] for item in self.calendar.values()).year
        self.sections = sorted({row['section'] for row in self.cut_rows})
        self.expected_levels = {bimester: {level: counts.get(level, 0) for level in LEVELS}
                                for bimester, counts in self.summary['verification']['recalculated_levels'].items()}
        if self.summary.get('rejected') is None or self.summary['verification'].get('mismatches'):
            raise StopRun('CONVERSION_SUMMARY_INCOHERENT')

    def _calendar(self):
        close_to_bimester = {row['closing_date']: row['bimester'] for row in self.close_rows}
        calendar = {}
        for row in self.cut_rows:
            bimester = close_to_bimester.get(row['target_date'])
            if bimester is None:
                raise StopRun('CALENDAR_INCOHERENT', 'target_date')
            item = calendar.setdefault(bimester, {'start': date.fromisoformat(row['window_start']), 'close': date.fromisoformat(row['target_date']),
                                                  'cutoff_at': row['cutoff_at'], 'rows': 0})
            if (item['start'], item['close'], item['cutoff_at']) != (date.fromisoformat(row['window_start']), date.fromisoformat(row['target_date']),
                                                                       row['cutoff_at']):
                raise StopRun('CALENDAR_INCOHERENT', bimester)
            item['rows'] += 1
        for bimester in calendar:
            rows = [row for row in self.close_rows if row['bimester'] == bimester]
            availability, scheduled = {row['closing_available_at'] for row in rows}, {int(row['days_scheduled']) for row in rows}
            if len(availability) != 1 or len(scheduled) != 1:
                raise StopRun('CALENDAR_INCOHERENT', bimester)
            calendar[bimester].update(closing_available_at=availability.pop(), scheduled_days=scheduled.pop(),
                                      closing_rows=len(rows))
        return dict(sorted(calendar.items()))

    def protocol(self, period_id):
        bimesters = []
        for code, item in self.calendar.items():
            available = datetime.fromisoformat(item['cutoff_at']).astimezone(LIMA).date()
            cutoff_date = available - timedelta(days=4)             # fecha de corte de los datos (17-04 y 26-06 del Excel)
            if not item['start'] <= cutoff_date < item['close'] or datetime.fromisoformat(item['closing_available_at']).astimezone(LIMA).date() < item['close']:
                raise StopRun('PROTOCOL_CALENDAR_INCOHERENT', code)
            bimesters.append(dict(code=code, start_date=item['start'].isoformat(), cutoff_date=cutoff_date.isoformat(),
                                  cutoff_available_at=item['cutoff_at'], close_date=item['close'].isoformat(),
                                  closing_available_at=item['closing_available_at'], scheduled_days=item['scheduled_days']))
        return dict(period_id=period_id, school_label='Colegio (cohorte real local)', cohort_label=f'3.º de secundaria {self.year}',
                    grade_scale_min=0, grade_scale_max=20, participation_min=1, participation_max=5, participation_labels=PARTICIPATION_LABELS,
                    bimesters=bimesters, source_label='Excel del colegio convertido con convert_real_excel (cortes y cierres)',
                    quality_rules={'unique_key': ['student', 'bimester'], 'converter': 'convert_real_excel'},
                    eligibility_rules=dict(inference_max_missing_fraction=0.4, required_features=['average_grade']),
                    risk_rule=dict(version='RIESGO_V1'), opportune_windows=dict(detection_days=0, intervention_days=14))


# ---------------------------------------------------------------- consultas SQL (solo lectura, números)
SQL = {
    'study': 'SELECT id::text AS id, comparison IS NOT NULL AS compared FROM risk_school.synthetic_studies WHERE period_id=CAST(:p AS uuid)',
    'batches': "SELECT count(*) AS n FROM risk_school.import_batches WHERE period_id=CAST(:p AS uuid) AND status='COMMITTED'",
    'references': 'SELECT count(DISTINCT snapshot_id) AS n FROM risk_school.risk_references WHERE period_id=CAST(:p AS uuid)',
    'counts': '''SELECT (SELECT count(DISTINCT e.student_id) FROM risk_school.enrollments e WHERE e.period_id=CAST(:p AS uuid)) AS students,
        (SELECT count(*) FROM risk_school.academic_snapshots WHERE period_id=CAST(:p AS uuid) AND data_origin='REAL') AS snapshots,
        (SELECT count(DISTINCT snapshot_id) FROM risk_school.risk_references WHERE period_id=CAST(:p AS uuid)) AS risk_references,
        (SELECT count(DISTINCT e.student_id) FROM risk_school.enrollments e JOIN risk_school.students s ON s.id=e.student_id
          WHERE e.period_id=CAST(:p AS uuid) AND s.is_active AND s.eligible_for_processing) AS eligible''',
    'distribution': '''SELECT rr.bimester, rr.risk_level, count(*) AS n FROM (SELECT DISTINCT ON (snapshot_id) * FROM risk_school.risk_references
        WHERE period_id=CAST(:p AS uuid) ORDER BY snapshot_id, revision DESC) rr GROUP BY 1,2''',
    'comparison': 'SELECT comparison->\'report\' AS report FROM risk_school.synthetic_studies WHERE period_id=CAST(:p AS uuid)',
    'models': '''SELECT m.id::text AS id, m.algorithm, m.is_active, m.manifest->>'approval_kind' AS approval_kind FROM risk_school.model_versions m
        JOIN risk_school.synthetic_studies st ON st.id=m.study_id WHERE st.period_id=CAST(:p AS uuid)''',
    'predictions': '''SELECT count(*) AS n FROM risk_school.predictions p JOIN risk_school.academic_snapshots sn ON sn.id=p.snapshot_id
        WHERE sn.period_id=CAST(:p AS uuid) AND sn.target_date=CAST(:close AS date)''',
    'clocks': '''SELECT (SELECT count(*) FROM risk_school.predictions p JOIN risk_school.academic_snapshots sn ON sn.id=p.snapshot_id
          WHERE sn.period_id=CAST(:p AS uuid)) AS predictions,
        (SELECT count(*) FROM risk_school.predictions p JOIN risk_school.academic_snapshots sn ON sn.id=p.snapshot_id
          WHERE sn.period_id=CAST(:p AS uuid) AND p.as_of_at < p.predicted_at - interval '1 day') AS simulated_predictions,
        (SELECT count(*) FROM risk_school.alerts a JOIN risk_school.enrollments e ON e.id=a.enrollment_id WHERE e.period_id=CAST(:p AS uuid)) AS alerts,
        (SELECT count(*) FROM risk_school.alerts a JOIN risk_school.enrollments e ON e.id=a.enrollment_id
          WHERE e.period_id=CAST(:p AS uuid) AND a.detected_at < a.opened_at - interval '1 day') AS simulated_alerts''',
    'pder': '''WITH ref AS (SELECT DISTINCT ON (snapshot_id) snapshot_id, enrollment_id, risk_level FROM risk_school.risk_references
          WHERE period_id=CAST(:p AS uuid) AND bimester=:b ORDER BY snapshot_id, revision DESC),
        pred AS (SELECT DISTINCT ON (snapshot_id) snapshot_id, risk_level, COALESCE(as_of_at, predicted_at) AS instant FROM risk_school.predictions
          WHERE data_origin='REAL' ORDER BY snapshot_id, predicted_at DESC)
        SELECT count(*) FILTER (WHERE ref.risk_level IN ('MEDIUM','HIGH')) AS denominator,
               count(*) FILTER (WHERE ref.risk_level IN ('MEDIUM','HIGH') AND pred.risk_level IN ('MEDIUM','HIGH')
                                AND pred.instant < CAST(:close AS timestamptz) - make_interval(days => CAST(:lead AS integer))) AS numerator
        FROM ref JOIN risk_school.enrollments e ON e.id=ref.enrollment_id JOIN risk_school.students s ON s.id=e.student_id
        LEFT JOIN pred ON pred.snapshot_id=ref.snapshot_id WHERE s.is_active AND s.eligible_for_processing''',
    'cra': '''SELECT count(*) AS denominator, count(*) FILTER (WHERE pr.risk_level='LOW' OR fd.decision IN ('CREATED','UPDATED')) AS numerator
        FROM risk_school.enrollments e JOIN risk_school.students s ON s.id=e.student_id
        JOIN risk_school.academic_snapshots sn ON sn.enrollment_id=e.id AND sn.target_date=CAST(:close AS date)
        LEFT JOIN LATERAL (SELECT p.id, p.risk_level FROM risk_school.predictions p WHERE p.snapshot_id=sn.id ORDER BY p.predicted_at DESC LIMIT 1) pr ON true
        LEFT JOIN risk_school.followup_decisions fd ON fd.prediction_id=pr.id
        WHERE e.period_id=CAST(:p AS uuid) AND s.is_active AND s.eligible_for_processing AND pr.risk_level IS NOT NULL''',
    'matrix': '''WITH ref AS (SELECT DISTINCT ON (snapshot_id) snapshot_id, risk_level FROM risk_school.risk_references
          WHERE period_id=CAST(:p AS uuid) AND bimester=:b ORDER BY snapshot_id, revision DESC),
        pred AS (SELECT DISTINCT ON (snapshot_id) snapshot_id, risk_level FROM risk_school.predictions WHERE data_origin='REAL' ORDER BY snapshot_id, predicted_at DESC)
        SELECT ref.risk_level AS reference, pred.risk_level AS predicted, count(*) AS n FROM ref LEFT JOIN pred ON pred.snapshot_id=ref.snapshot_id
        GROUP BY 1,2''',
}


EXEC_SQL = r'''
import json, sys
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
p = json.load(sys.stdin)
assert p['sql'].lstrip().lower().startswith(('select', 'with'))
db = Database(Settings())
def plain(v):
    return str(v) if isinstance(v, (Decimal, date, datetime)) else v
with db.session_factory() as s:
    rows = [{k: plain(v) for k, v in row._mapping.items()} for row in s.execute(text(p['sql']), p['params'])]
print(json.dumps(rows))
'''


LOCKED_TUTOR = r'''
import json, secrets, sys
from sqlalchemy import select
from app.configure_context import UserInput, configure
from app.core.config import Settings
from app.core.database import Database
from app.models.s1 import AppUser
p = json.load(sys.stdin)
db = Database(Settings())
with db.session_factory() as s:
    actor = s.scalar(select(AppUser).where(AppUser.email == p['actor_email'], AppUser.role == 'ADMIN', AppUser.is_active))
    tutor = s.scalar(select(AppUser).where(AppUser.email == 'tutor-bloqueado@example.com'))
    if tutor is None:
        identifier = configure(s, actor, UserInput(email='tutor-bloqueado@example.com', display_name='Tutor sin acceso (relleno)',
                                                   role='TUTOR', password=secrets.token_urlsafe(32)))
    else:
        identifier = tutor.id
print(json.dumps({'id': str(identifier)}))
'''


class Live:
    """Acceso real al destino aislado: sesión ADMIN con el perfil Windows, órdenes internas y consultas de solo lectura."""

    def __init__(self, target, account):
        self.target, self.account = target, account
        self.client = self.csrf = None

    def __enter__(self):
        import study
        from operator_profiles import SessionClient
        self.study = study
        self.target.assert_identity()
        self.client = SessionClient(self.target)
        status, login = self.client.request('POST', '/auth/login', self.account, {'Origin': self.target.web_url})
        if status != 200 or login.get('user', {}).get('role') != 'ADMIN':
            raise StopRun('ADMIN_AUTHENTICATION_REQUIRED')
        self.csrf = login['csrf_token']
        return self

    def __exit__(self, *exc):
        if self.csrf:
            self.client.request('POST', '/auth/logout', headers={'X-CSRF-Token': self.csrf})
        return False

    def api(self, method, path, body=None):
        headers = {'Origin': self.target.web_url}
        if method != 'GET':
            headers['X-CSRF-Token'] = self.csrf
        return self.client.request(method, path, body, headers)

    def raw_get(self, path):
        import urllib.request
        request = urllib.request.Request(self.client.base_url + '/api/v1' + path, headers={'Origin': self.target.web_url})
        with self.client.opener.open(request, timeout=60) as response:
            return response.read()

    def import_csv(self, period_id, content):
        status, batch = self.study.multipart(self.client, period_id, content, self.csrf)
        if status not in (200, 201):
            raise StopRun((batch or {}).get('code', 'IMPORT_PREVIEW_FAILED'))
        return batch

    def internal(self, command, payload):
        try:
            return self.study.internal(command, self.account, target=self.target, **payload)
        except RuntimeError as error:
            raise StopRun(str(error)) from None

    def sql(self, name, **params):
        try:
            return self.target.api_python(EXEC_SQL, {'sql': SQL[name], 'params': params})
        except RuntimeError as error:
            raise StopRun(str(error)) from None

    def load_closings(self, period_id, rows):
        try:
            return self.target.api_python(load_closings.CODE, {'period_id': period_id, 'actor_email': self.account['email'], 'rows': rows})
        except RuntimeError as error:
            raise StopRun(str(error)) from None

    def create_locked_tutor(self):
        """Cuenta TUTOR de relleno con contraseña aleatoria que nadie conoce (no se guarda ni se imprime): solo permite que existan las secciones."""
        try:
            return self.target.api_python(LOCKED_TUTOR, {'actor_email': self.account['email']})['id']
        except RuntimeError as error:
            raise StopRun(str(error)) from None

    def head(self):
        """La cuenta de la aplicación no lee `alembic_version`: se reconoce 0008 por sus objetos (regla de modelo activo por origen)."""
        rows = self.target.api_python(EXEC_SQL, {'sql': """SELECT (SELECT count(*) FROM pg_constraint WHERE conname='active_model_scope')
            + (SELECT count(*) FROM pg_indexes WHERE indexname='ux_active_model_origin') AS n""", 'params': {}})
        return '0008_real_chain' if int(rows[0]['n']) == 2 else 'UNKNOWN'


# ---------------------------------------------------------------- orquestación
def check_pre_backup(manifest, project, now=None, max_age_hours=PRE_BACKUP_MAX_AGE_HOURS):
    """El respaldo previo a cargar datos REAL en la instalación activa: de ese proyecto, en 0008 y reciente. Devuelve su identificador."""
    if (manifest.get('source') or {}).get('project') != project:
        raise StopRun('PRE_BACKUP_OTHER_INSTALLATION')
    if manifest.get('migration') != PRE_BACKUP_HEAD:
        raise StopRun('PRE_BACKUP_NOT_AT_0008')
    try:
        created = datetime.fromisoformat(manifest['created_at'])
    except (KeyError, TypeError, ValueError):
        raise StopRun('PRE_BACKUP_DATE_INVALID') from None
    if created.tzinfo is None:
        raise StopRun('PRE_BACKUP_DATE_INVALID')
    age = (now or datetime.now(timezone.utc)) - created
    if not timedelta(0) <= age <= timedelta(hours=max_age_hours):
        raise StopRun('PRE_BACKUP_TOO_OLD', f'más de {max_age_hours} h o fecha futura')
    return manifest['id']


def load_pre_backup(path):
    """Descifra (DPAPI) y valida el paquete propio; solo Windows. La importación es perezosa para no exigirla a quien no usa la activa."""
    import backup_restore
    try:
        return backup_restore.verified_content(path)[1]
    except RuntimeError as error:
        code = str(error)
        raise StopRun(code if re.fullmatch(r'[A-Z0-9_]{1,100}', code) else 'PRE_BACKUP_INVALID') from None


def guard_active(project, confirm, pre_backup, emit=print, now=None):
    """Condiciones para cargar datos REAL en la instalación de siempre: confirmación con su nombre y respaldo verificado reciente."""
    if confirm != project:
        raise StopRun('ACTIVE_CONFIRMATION_REQUIRED', f'Repite con --confirm-active {project} y --pre-backup <respaldo verificado>.', exit_code=3)
    if pre_backup is None:
        raise StopRun('PRE_BACKUP_REQUIRED', 'Crea y verifica un respaldo (backup_restore.py backup y verify) y pásalo con --pre-backup.', exit_code=3)
    manifest = load_pre_backup(pre_backup)
    backup_id = check_pre_backup(manifest, project, now)
    emit(json.dumps({'step': 'active_guard', 'status': 'OK', 'pre_backup_id': backup_id, 'pre_backup_origin': manifest.get('origin')},
                    ensure_ascii=True, sort_keys=True))
    return backup_id


class Runner:
    def __init__(self, gateway, inputs, results, *, dry_run=False, confirm_protocol=False, tutors=(None, None), locked_tutor=False, active=False,
                 emit=print):
        self.g, self.inputs, self.results = gateway, inputs, Path(results)
        self.dry_run, self.confirm, self.tutors, self.emit = dry_run, confirm_protocol, tutors, emit
        self.locked_tutor, self.active = locked_tutor, active
        self.steps, self.state = [], {}

    def step(self, name, status, **counts):
        self.steps.append({'step': name, 'status': status, **counts})
        self.emit(json.dumps({'step': name, 'status': status, **counts}, ensure_ascii=True, sort_keys=True))

    def write(self, name, content):
        if self.dry_run:
            return
        self.results.mkdir(parents=True, exist_ok=True)
        (self.results / name).write_bytes((content if isinstance(content, str) else json.dumps(content, ensure_ascii=True, indent=2, sort_keys=True) + '\n').encode('utf-8'))

    # 0
    def tutor_decided(self):
        """Hay decisión explícita sobre el tutor: relleno bloqueado o un tutor indicado para cada sección."""
        paired = dict(zip(self.inputs.sections, self.tutors))
        return bool(self.locked_tutor or (len(paired) == len(self.inputs.sections) and all(paired.values())))

    def preflight(self):
        if self.g.head() != '0008_real_chain':
            raise StopRun('TARGET_NOT_AT_0008')
        if self.active and not self.dry_run and not self.tutor_decided():
            # Antes de escribir nada: en la activa no se elige solo al único tutor existente.
            raise StopRun('ACTIVE_TUTOR_EXPLICIT_REQUIRED', 'En la instalación activa indica --tutor-a y --tutor-b, o usa --locked-tutor.')
        self.step('preflight', 'OK', input_hashes='VERIFIED', rows=len(self.inputs.cut_rows), students=len(self.inputs.codes),
                  bimesters=len(self.inputs.calendar))

    # 1
    def period(self):
        code = PERIOD_CODE.format(year=self.inputs.year)
        status, periods = self.g.api('GET', '/periods')
        found = next((item for item in periods if item['code'] == code and item['data_origin'] == 'REAL'), None)
        if found:
            self.state['period'] = found
            return self.step('period', 'REUSED')
        if self.dry_run:
            return self.step('period', 'PENDING')
        status, created = self.g.api('POST', '/periods', dict(creation_key=key('period', code), code=code, school_year=self.inputs.year,
                                     start_date=f'{self.inputs.year}-01-01', end_date=f'{self.inputs.year}-12-31', data_origin='REAL'))
        if status != 200:
            raise StopRun('PERIOD_CREATE_FAILED', (created or {}).get('code'))
        self.state['period'] = created
        self.step('period', 'DONE')

    # 2
    def sections(self):
        period = self.state.get('period')
        if period is None:
            return self.step('sections', 'PENDING')
        status, sections = self.g.api('GET', f"/sections?period_id={period['id']}")
        have = {item['code'] for item in sections if item['grade'] == SECTION_GRADE}
        missing = [code for code in self.inputs.sections if code not in have]
        if not missing:
            return self.step('sections', 'REUSED', sections=len(have))
        tutor_by_section = dict(zip(self.inputs.sections, self.tutors))
        if any(tutor_by_section.get(code) is None for code in missing):
            if self.active:
                # Instalación activa: nunca se asigna por defecto al único tutor existente (ganaría acceso a datos REAL sin que se decida).
                if not self.locked_tutor:
                    if self.dry_run:
                        return self.step('sections', 'PENDING', missing=len(missing), tutor='EXPLICIT_REQUIRED')
                    raise StopRun('ACTIVE_TUTOR_EXPLICIT_REQUIRED', 'En la instalación activa indica --tutor-a y --tutor-b, o usa --locked-tutor.')
                ids = []
            else:
                _, tutors = self.g.api('GET', '/catalogs/tutors')
                ids = [item['id'] for item in tutors]
            if len(ids) == 1:
                tutor_by_section = {code: ids[0] for code in self.inputs.sections}
            elif len(ids) < 1 and self.locked_tutor:
                if self.dry_run:
                    return self.step('sections', 'PENDING', missing=len(missing), tutor='LOCKED_PLACEHOLDER')
                placeholder = self.g.create_locked_tutor()
                tutor_by_section = {code: placeholder for code in self.inputs.sections}
            elif len(ids) < 1:
                raise StopRun('TUTOR_REQUIRED', 'Crea una cuenta TUTOR (runtime_target.py configure), indica --tutor-a/--tutor-b o usa --locked-tutor.')
            else:
                raise StopRun('TUTOR_CHOICE_REQUIRED', 'Hay varios tutores: indica --tutor-a y --tutor-b.')
        if self.dry_run:
            return self.step('sections', 'PENDING', missing=len(missing))
        for code in missing:
            status, created = self.g.api('POST', '/sections', dict(creation_key=key('section', code), code=code, grade=SECTION_GRADE,
                                         school_year=self.inputs.year, tutor_id=tutor_by_section[code], data_origin='REAL'))
            if status != 200:
                raise StopRun('SECTION_CREATE_FAILED', (created or {}).get('code'))
        self.step('sections', 'DONE', created=len(missing))

    # 3
    def protocol(self):
        period = self.state.get('period')
        if period is None:
            return self.step('protocol', 'PENDING')
        wanted = self.inputs.protocol(period['id'])
        status, found = self.g.api('GET', f"/processing-protocols?period_id={period['id']}")
        created = False
        if status == 404:
            if self.dry_run:
                return self.step('protocol', 'PENDING')
            status, found = self.g.api('POST', '/processing-protocols', wanted)
            if status != 200:
                raise StopRun('PROTOCOL_CREATE_FAILED', (found or {}).get('code'))
            created = True
        elif status != 200:
            raise StopRun('PROTOCOL_READ_FAILED')
        same = ([(b['code'], b['close_date'], b['cutoff_available_at'][:10]) for b in found['bimesters']] ==
                [(b['code'], b['close_date'], b['cutoff_available_at'][:10]) for b in wanted['bimesters']]
                and found['participation_max'] == 5 and str(found['grade_scale_max']).startswith('20'))
        if not same:
            raise StopRun('PROTOCOL_PARAMS_DIFFER')
        if not found['authorization_confirmed_by_admin']:
            if not self.confirm:
                if self.dry_run:
                    return self.step('protocol', 'PENDING', confirmed=False)
                raise StopRun('PROTOCOL_CONFIRMATION_REQUIRED', 'Revisa el protocolo y vuelve a ejecutar con --confirm-protocol.', exit_code=3)
            if self.dry_run:
                return self.step('protocol', 'PENDING', confirmed=False)
            status, found = self.g.api('POST', f"/processing-protocols/{found['id']}/confirm", {})
            if status != 200 or not found['authorization_confirmed_by_admin']:
                raise StopRun('PROTOCOL_CONFIRM_FAILED')
            self.state['protocol'] = found
            return self.step('protocol', 'DONE', confirmed=True, created=created)
        self.state['protocol'] = found
        self.step('protocol', 'REUSED', confirmed=True)

    # 4
    def study(self):
        protocol, period = self.state.get('protocol'), self.state.get('period')
        if not protocol or not protocol['authorization_confirmed_by_admin']:
            return self.step('study', 'PENDING')
        rows = self.g.sql('study', p=period['id'])
        if rows:
            self.state['study_id'] = rows[0]['id']
            return self.step('study', 'REUSED')
        if self.dry_run:
            return self.step('study', 'PENDING')
        result = self.g.internal('register-study', {'protocol_id': protocol['id'], 'csv_base64': base64.b64encode(self.inputs.cortes).decode()})
        self.state['study_id'] = result['study_id']
        self.step('study', 'DONE', rows=result['rows'], students=result['students'], horizon_days=result['horizon_days'])

    # 5
    def importing(self):
        if 'study_id' not in self.state:
            return self.step('import', 'PENDING')
        period = self.state['period']
        if self.g.sql('batches', p=period['id'])[0]['n']:
            return self.step('import', 'REUSED')
        if self.dry_run:
            return self.step('import', 'PENDING')
        batch = self.g.import_csv(period['id'], self.inputs.cortes)
        if batch['status'] != 'READY' or batch['data_origin'] != 'REAL':
            raise StopRun('IMPORT_NOT_READY', batch.get('status'))
        status, commit = self.g.api('POST', f"/imports/{batch['id']}/commit", {'expected_preview_version': batch['preview_version']})
        if status != 200:
            raise StopRun('IMPORT_COMMIT_FAILED', (commit or {}).get('code'))
        self.step('import', 'DONE', total_rows=batch['total_rows'], created_snapshots=commit['created_snapshots'])

    # 6
    def closings(self):
        if 'study_id' not in self.state or not self.g.sql('batches', p=self.state['period']['id'])[0]['n']:
            return self.step('closings', 'PENDING')
        period = self.state['period']
        have = self.g.sql('references', p=period['id'])[0]['n']
        if have >= len(self.inputs.close_rows):
            return self.step('closings', 'REUSED', references=have)
        if self.dry_run:
            return self.step('closings', 'PENDING')
        parsed = load_closings.parse_csv(self.inputs.cierres_path)
        rows = [{k: (str(v) if not isinstance(v, (int, str)) else v) for k, v in row.items()} for row in parsed]
        result = self.g.load_closings(period['id'], rows)
        self.step('closings', 'DONE', created=result['created'], reused=result['reused'])

    # 7
    def checks(self):
        if 'study_id' not in self.state or not self.g.sql('references', p=self.state['period']['id'])[0]['n']:
            return self.step('checks', 'PENDING')
        period = self.state['period']
        counts = self.g.sql('counts', p=period['id'])[0]
        expected = {'students': len(self.inputs.codes), 'snapshots': len(self.inputs.cut_rows), 'risk_references': len(self.inputs.close_rows),
                    'eligible': len(self.inputs.codes)}
        if {k: int(counts[k]) for k in expected} != expected:
            raise StopRun('IMPORT_COUNTS_MISMATCH', {k: int(counts[k]) for k in expected})
        found = {}
        for row in self.g.sql('distribution', p=period['id']):
            found.setdefault(row['bimester'], {level: 0 for level in LEVELS})[row['risk_level']] = int(row['n'])
        if found != self.inputs.expected_levels:
            raise StopRun('REFERENCE_DISTRIBUTION_MISMATCH', found)
        self.state['counts'] = {k: int(counts[k]) for k in expected}
        self.state['distribution'] = found
        self.step('checks', 'OK', **self.state['counts'], distribution={b: [found[b][level] for level in LEVELS] for b in sorted(found)})

    # 8
    def comparison(self):
        if 'distribution' not in self.state:
            return self.step('comparison', 'PENDING')
        period = self.state['period']
        if self.g.sql('study', p=period['id'])[0]['compared']:
            status = 'REUSED'
        elif self.dry_run:
            return self.step('comparison', 'PENDING')
        else:
            self.g.internal('compare', {'study_id': self.state['study_id'], 'leave_one_student_out': True})
            status = 'DONE'
        report = self.g.sql('comparison', p=period['id'])[0]['report']
        report = json.loads(report) if isinstance(report, str) else report
        self.write('comparacion_modelos_completa.json', report)
        self.state['table'] = model_table(report)
        self.state['report'] = {k: report[k] for k in ('selected_algorithm', 'selection_rule', 'repetitions', 'requested_folds', 'students',
                                                       'observations', 'support_by_class', 'warnings', 'approval_kind', 'seed')}
        self.step('comparison', status, selected=report['selected_algorithm'], repetitions=report['repetitions'])

    # 9
    def model(self):
        if 'table' not in self.state:
            return self.step('model', 'PENDING')
        period = self.state['period']
        models = self.g.sql('models', p=period['id'])
        active = next((m for m in models if m['is_active']), None)
        if active:
            self.state['model'] = active
            return self.step('model', 'REUSED', algorithm=active['algorithm'], approval_kind=active['approval_kind'])
        if self.dry_run:
            return self.step('model', 'PENDING')
        registered = self.g.internal('register', {'study_id': self.state['study_id'], 'algorithm': None})
        activated = self.g.internal('activate', {'model_id': registered['model_id']})
        self.state['model'] = {'algorithm': registered['algorithm'], 'approval_kind': activated['approval_kind']}
        self.step('model', 'DONE', algorithm=registered['algorithm'], approval_kind=activated['approval_kind'])

    # 10
    def evaluation(self):
        if 'model' not in self.state:
            return self.step('evaluation', 'PENDING')
        period, runs = self.state['period'], {}
        for bimester, item in self.inputs.calendar.items():
            done = self.g.sql('predictions', p=period['id'], close=item['close'].isoformat())[0]['n']
            if done >= item['rows']:
                runs[bimester] = {'status': 'REUSED', 'predictions': int(done)}
                continue
            if self.dry_run:
                runs[bimester] = {'status': 'PENDING'}
                continue
            status, out = self.g.api('POST', '/predictions/run', {'period_id': period['id'], 'as_of': item['cutoff_at']})
            if status != 200:
                raise StopRun('PREDICTION_RUN_FAILED', (out or {}).get('code'))
            runs[bimester] = {'status': 'DONE', 'selected': out['selected'], 'created': out['created'], 'reused': out['reused'],
                              'abstentions': len(out['abstentions']), 'alerts_created': out['followup']['created'],
                              'alerts_updated': out['followup']['updated'], 'retained_low': out['followup']['retained_low'],
                              'no_alert': out['followup']['no_alert']}
        if any(item['status'] == 'PENDING' for item in runs.values()):
            return self.step('evaluation', 'PENDING')
        clocks = self.g.sql('clocks', p=period['id'])[0]
        if int(clocks['simulated_predictions']) != int(clocks['predictions']) or int(clocks['simulated_alerts']) != int(clocks['alerts']):
            raise StopRun('RETROSPECTIVE_CLOCKS_INVALID')
        self.state['runs'], self.state['clocks'] = runs, {k: int(v) for k, v in clocks.items()}
        self.step('evaluation', 'DONE' if any(item['status'] == 'DONE' for item in runs.values()) else 'REUSED',
                  runs={b: item['status'] for b, item in runs.items()}, clocks=self.state['clocks'])

    # 11 + 12
    def indicators(self):
        if 'runs' not in self.state:
            return self.step('indicators', 'PENDING')
        period, protocol = self.state['period'], self.state['protocol']
        lead = protocol['opportune_windows']['detection_days']
        per_bimester = {}
        for bimester, item in self.inputs.calendar.items():
            status, data = self.g.api('GET', f"/indicators?period_id={period['id']}&bimester={bimester}")
            if status != 200:
                raise StopRun('INDICATORS_FAILED', (data or {}).get('code'))
            self.write(f'indicadores_{bimester}.json', data)
            self.write(f'indicadores_{bimester}_alumnos.csv', self.g.raw_get(f"/indicators/export.csv?period_id={period['id']}&bimester={bimester}").decode('utf-8'))
            self.write(f'indicadores_{bimester}_intervenciones.csv', self.g.raw_get(f"/indicators/interventions.csv?period_id={period['id']}").decode('utf-8'))
            close_instant = (datetime.combine(item['close'], datetime.min.time(), tzinfo=LIMA) + timedelta(days=1)).isoformat()
            sql_pder = self.g.sql('pder', p=period['id'], b=bimester, close=close_instant, lead=lead)[0]
            sql_cra = self.g.sql('cra', p=period['id'], close=item['close'].isoformat())[0]
            matrix = {level: {name: 0 for name in (*LEVELS, 'NONE')} for level in LEVELS}
            for row in self.g.sql('matrix', p=period['id'], b=bimester):
                matrix[row['reference']][row['predicted'] or 'NONE'] += int(row['n'])
            total = data['total']
            system = {'pder': [total['pder']['numerator'], total['pder']['denominator']], 'cra': [total['cra']['numerator'], total['cra']['denominator']]}
            independent = {'pder': [int(sql_pder['numerator']), int(sql_pder['denominator'])], 'cra': [int(sql_cra['numerator']), int(sql_cra['denominator'])]}
            per_bimester[bimester] = {'eligible': data['total']['eligible_students'], 'system': system, 'sql': independent, 'agree': system == independent,
                                      'matrix_reference_by_predicted': matrix, 'retrospective_alerts': data['retrospective_alerts'],
                                      'nia': {'value': total['nia']['mean'], 'reason': total['nia']['reason']},
                                      'opportune': {'percent': total['opportune']['percent'], 'reason': total['opportune']['reason']},
                                      # PRV no se informa: el sistema solo ve el CSV ya filtrado por el conversor; la recepción real (126 recibidas) no tiene procedencia confirmada.
                                      'prv': {'percent': data['prv']['percent'], 'reason': data['prv']['reason']},
                                      'out_of_fold_basis': total['metric_basis'], 'run': self.state['runs'][bimester]}
        self.state['indicators'] = per_bimester
        self.step('indicators', 'DONE', bimesters=sorted(per_bimester), sql_matches_system=all(item['agree'] for item in per_bimester.values()))

    def aggregate(self):
        """Resumen agregado SIN códigos de alumno ni nombres: apto para guardarse junto al repositorio."""
        if 'indicators' not in self.state:
            return None
        summary = {'reading': 'Simulación retrospectiva con datos reales del colegio; no mide impacto del sistema. Análisis exploratorio local.',
                   'counts': self.state['counts'], 'reference_distribution_low_medium_high': {b: [v[level] for level in LEVELS]
                                                                                            for b, v in self.state['distribution'].items()},
                   'comparison': {**self.state['report'], 'models': self.state['table']}, 'active_model': self.state['model'],
                   'retrospective_clocks': self.state['clocks'], 'indicators': self.state['indicators'],
                   'unavailable': {'NIA': 'NO_REAL_INTERVENTIONS', 'intervencion_oportuna': 'NO_REAL_INTERVENTIONS',
                                   'backup_restore_real_data': 'NOT_IMPLEMENTED'}}
        text = json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
        leaked = [code for code in self.inputs.codes if code in text]
        if leaked:
            raise StopRun('AGGREGATE_CONTAINS_STUDENT_CODES')
        return summary

    def run(self):
        self.preflight()
        for step in (self.period, self.sections, self.protocol, self.study, self.importing, self.closings, self.checks, self.comparison,
                     self.model, self.evaluation, self.indicators):
            step()
        summary = self.aggregate()
        if summary is not None:
            self.write('resumen_agregado.json', summary)
        return summary


def spread_text(item):
    return {'mean': item['mean'], 'sd': item['sd']}


def model_table(report):
    """Tabla agregada por modelo (media y desviación entre repeticiones); sin códigos de alumno."""
    table = {}
    for name, item in report['algorithms'].items():
        cv = item['repeated_cv']
        table[name] = {'accuracy': spread_text(cv['accuracy']), 'macro_f1': spread_text(cv['macro']['f1']),
                       'cohen_kappa': spread_text(cv['cohen_kappa']) if 'cohen_kappa' in cv else None,
                       'recall_high': spread_text(cv['per_class']['HIGH']['recall']),
                       'balanced_accuracy': spread_text(cv['balanced_accuracy']),
                       'aggregated_confusion_matrix': cv['aggregated_confusion_matrix']}
        if 'leave_one_student_out' in item:
            loso = item['leave_one_student_out']
            table[name]['leave_one_student_out'] = {'accuracy': loso['accuracy'], 'macro_f1': loso['macro']['f1'],
                                                    'recall_high': loso['per_class']['HIGH']['recall']}
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--operator-profile', required=True)
    parser.add_argument('--input', type=Path, required=True, help='Carpeta con cortes.csv, cierres.csv y resumen_conversion.json')
    parser.add_argument('--results', type=Path, required=True, help='Carpeta de resultados FUERA de Git')
    parser.add_argument('--dry-run', action='store_true', help='Valida archivos y destino sin escribir nada')
    parser.add_argument('--confirm-protocol', action='store_true', help='Confirma el protocolo REAL si aún no lo está (acción de ADMIN)')
    parser.add_argument('--tutor-a'); parser.add_argument('--tutor-b')
    parser.add_argument('--locked-tutor', action='store_true', help='Si no hay tutores (en la activa: siempre, salvo --tutor-a/--tutor-b), crea una cuenta TUTOR '
                        'de relleno sin acceso (contraseña aleatoria desconocida)')
    parser.add_argument('--confirm-active', help='Solo destino ACTIVE: repite aquí el nombre del proyecto (riesgo-escolar) para autorizar la carga REAL sobre él')
    parser.add_argument('--pre-backup', type=Path, help='Solo destino ACTIVE: respaldo S6 verificado (.sebackup) de ese proyecto, en 0008 y de menos de 24 h')
    parser.add_argument('--public-summary', type=Path, help='Copia el resumen agregado (sin códigos) a este archivo')
    args = parser.parse_args(argv)
    try:
        if converter.inside_git_tree(args.results):
            raise StopRun('RESULTS_INSIDE_GIT')
        inputs = Inputs(args.input)
        from operator_profiles import admin_account
        from runtime_target import Target
        target = Target.load(args.target)
        active = target.kind == 'ACTIVE'
        if active and not args.dry_run:
            guard_active(target.project, args.confirm_active, args.pre_backup)
        account = admin_account(target, operator_profile=args.operator_profile)
        with Live(target, account) as gateway:
            summary = Runner(gateway, inputs, args.results, dry_run=args.dry_run, confirm_protocol=args.confirm_protocol,
                             tutors=(args.tutor_a, args.tutor_b), locked_tutor=args.locked_tutor, active=active).run()
        if summary is not None and args.public_summary and not args.dry_run:
            args.public_summary.write_text(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except StopRun as stop:
        print(json.dumps({'code': stop.code, **({'detail': stop.detail} if stop.detail else {})}, ensure_ascii=True, default=str))
        return stop.exit_code
    except RuntimeError as error:
        code = str(error)
        print(json.dumps({'code': code if re.fullmatch(r'[A-Z0-9_]{1,100}', code) else 'RUN_REAL_STUDY_FAILED'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
