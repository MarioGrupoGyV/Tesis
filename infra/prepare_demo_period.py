"""Periodo «Demostración en vivo»: estudio SINTÉTICO rotulado en una instalación AISLADA de demostración (instalación hermana).

    py -3.12 infra/prepare_demo_period.py --target <destino.json> --operator-profile <perfil> --confirm-demo-target <proyecto>
                                          [--period-code DEMO-VIVO] [--seed 1729] [--students N] [--repetitions N]
                                          [--tutor-id <uuid> | --locked-tutor] [--dry-run]

Genera el estudio sintético, importa su CSV exacto, compara, registra y activa el modelo sintético y renombra el periodo (solo su código visible).
Es idempotente: cada paso reconoce su estado y no se repite. El periodo trae los estudiantes SINTÉTICOS del generador (los necesita el modelo);
no crea ningún otro: el estudiante de la demostración lo registra el usuario en vivo.
Nunca actúa sobre el destino ACTIVE (la instalación de siempre solo tiene datos reales) y exige repetir el nombre del proyecto del destino
(`--confirm-demo-target`) para escribir; con `--dry-run` no escribe nada. Imprime solo estados y conteos: nunca filas ni códigos de alumno.
La contraseña del ADMIN sale del perfil Windows existente, jamás de argumentos.
"""
import argparse
import base64
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_real_study import EXEC_SQL, Live, StopRun, key  # noqa: E402

DEFAULT_CODE = 'DEMO-VIVO'
CODE_PATTERN = re.compile(r'^[A-Z0-9][A-Z0-9-]{1,38}$')
SQL = {
    'study': '''SELECT id::text AS id, period_id::text AS period_id, jsonb_array_length(COALESCE(bindings, '[]'::jsonb)) AS bound,
        comparison IS NOT NULL AS compared FROM risk_school.synthetic_studies
        WHERE data_origin='SYNTHETIC' AND kind='SYNTHETIC_STUDY' ORDER BY created_at LIMIT 1''',
    'models': '''SELECT id::text AS id, algorithm, is_active FROM risk_school.model_versions WHERE study_id=CAST(:s AS uuid) AND data_origin='SYNTHETIC' ''',
    'students': '''SELECT count(DISTINCT e.student_id) AS n FROM risk_school.enrollments e WHERE e.period_id=CAST(:p AS uuid)''',
}


class DemoLive(Live):
    """Mismo acceso que la corrida real (sesión ADMIN por perfil, órdenes internas) con las consultas de solo lectura de este script."""

    def sql(self, name, **params):
        try:
            return self.target.api_python(EXEC_SQL, {'sql': SQL[name], 'params': params})
        except RuntimeError as error:
            raise StopRun(str(error)) from None


class DemoRunner:
    def __init__(self, gateway, *, period_code=DEFAULT_CODE, seed=1729, students=None, repetitions=None, tutor_id=None, locked_tutor=False,
                 dry_run=False, emit=print):
        self.g, self.code, self.seed, self.students, self.repetitions = gateway, period_code, seed, students, repetitions
        self.tutor_id, self.locked_tutor, self.dry_run, self.emit = tutor_id, locked_tutor, dry_run, emit
        self.steps, self.state = [], {}

    def step(self, name, status, **counts):
        self.steps.append({'step': name, 'status': status, **counts})
        self.emit(json.dumps({'step': name, 'status': status, **counts}, ensure_ascii=True, sort_keys=True))

    # 0
    def preflight(self):
        if self.g.head() != '0008_real_chain':
            raise StopRun('TARGET_NOT_AT_0008')
        if not CODE_PATTERN.fullmatch(self.code):
            raise StopRun('PERIOD_CODE_INVALID')
        self.step('preflight', 'OK', period_code=self.code)

    # 1
    def tutor(self):
        """Tutor de la primera sección sintética: indicado, el relleno bloqueado o el único tutor existente (nunca se elige entre varios)."""
        if self.tutor_id:
            self.state['tutor'] = self.tutor_id
            return self.step('tutor', 'EXPLICIT')
        if self.state.get('study'):
            return self.step('tutor', 'NOT_NEEDED')                        # el estudio ya existe: la sección ya tiene su tutor
        _, tutors = self.g.api('GET', '/catalogs/tutors')
        ids = [item['id'] for item in tutors]
        if self.locked_tutor:
            if self.dry_run:
                return self.step('tutor', 'PENDING', source='LOCKED_PLACEHOLDER')
            self.state['tutor'] = self.g.create_locked_tutor()
            return self.step('tutor', 'LOCKED_PLACEHOLDER')
        if len(ids) == 1:
            self.state['tutor'] = ids[0]
            return self.step('tutor', 'SINGLE_EXISTING')
        if not ids:
            raise StopRun('TUTOR_REQUIRED', 'Indica --tutor-id o usa --locked-tutor (cuenta de relleno sin acceso).')
        raise StopRun('TUTOR_CHOICE_REQUIRED', 'Hay varios tutores: indica --tutor-id.')

    # 2
    def study(self):
        rows = self.g.sql('study')
        if rows:
            self.state['study'] = rows[0]
            return self.step('study', 'REUSED')
        return None

    def generate(self):
        if 'study' in self.state:
            return
        if self.dry_run:
            return self.step('study', 'PENDING')
        result = self.g.internal('generate', {'seed': self.seed, 'student_count': self.students, 'tutor_id': self.state.get('tutor')})
        self.state['study'] = {'id': result['study_id'], 'period_id': result['period_id'], 'bound': 0, 'compared': False}
        self.step('study', 'DONE')

    # 3
    def importing(self):
        study = self.state.get('study')
        if not study:
            return self.step('import', 'PENDING')
        if study['bound']:
            return self.step('import', 'REUSED', rows=study['bound'])
        if self.dry_run:
            return self.step('import', 'PENDING')
        export = self.g.internal('export-csv', {'study_id': study['id']})
        content = base64.b64decode(export['csv_base64'])
        batch = self.g.import_csv(export['period_id'], content)
        if batch['status'] not in ('READY', 'COMMITTED'):
            raise StopRun('IMPORT_NOT_READY', batch.get('status'))
        if batch['status'] == 'READY':
            status, commit = self.g.api('POST', f"/imports/{batch['id']}/commit", {'expected_preview_version': batch['preview_version']})
            if status != 200:
                raise StopRun('IMPORT_COMMIT_FAILED', (commit or {}).get('code'))
        study['bound'] = batch['total_rows']
        self.step('import', 'DONE', total_rows=batch['total_rows'])

    # 4
    def comparing(self):
        study = self.state.get('study')
        if not study or not study['bound']:
            return self.step('compare', 'PENDING')
        if study['compared']:
            return self.step('compare', 'REUSED')
        if self.dry_run:
            return self.step('compare', 'PENDING')
        payload = {'study_id': study['id'], 'algorithm': None}
        if self.repetitions:
            payload['repetitions'] = self.repetitions
        result = self.g.internal('compare', payload)
        study['compared'] = True
        self.step('compare', 'DONE', selected=result.get('selected_algorithm'))

    # 5 + 6
    def model(self):
        study = self.state.get('study')
        if not study or not study['compared']:
            return self.step('model', 'PENDING')
        models = self.g.sql('models', s=study['id'])
        active = next((item for item in models if item['is_active']), None)
        if active:
            self.state['model'] = active
            return self.step('model', 'REUSED', algorithm=active['algorithm'])
        if self.dry_run:
            return self.step('model', 'PENDING')
        registered = models[0] if models else self.g.internal('register', {'study_id': study['id'], 'algorithm': None})
        model_id = registered.get('model_id') or registered.get('id')
        activated = self.g.internal('activate', {'model_id': model_id})
        self.state['model'] = {'algorithm': registered['algorithm'], 'is_active': True}
        self.step('model', 'DONE', algorithm=registered['algorithm'], approval_kind=activated.get('approval_kind'))

    # 7
    def labeling(self):
        study = self.state.get('study')
        if not study:
            return self.step('label', 'PENDING')
        _, periods = self.g.api('GET', '/periods')
        mine = next((item for item in periods if item['id'] == study['period_id']), None)
        if mine is None:
            raise StopRun('DEMO_PERIOD_NOT_FOUND')
        if mine['code'] == self.code:
            self.state['period'] = mine
            return self.step('label', 'REUSED', period_code=self.code)
        if any(item['code'] == self.code for item in periods):
            raise StopRun('PERIOD_CODE_IN_USE')
        if self.dry_run:
            return self.step('label', 'PENDING', period_code=self.code)
        body = {key_: mine[key_] for key_ in ('school_year', 'start_date', 'end_date', 'data_origin', 'is_locked')}
        status, renamed = self.g.api('PATCH', f"/periods/{mine['id']}", {**body, 'code': self.code, 'expected_version': mine['version'],
                                                                         'creation_key': key('demo-period-code', self.code, mine['id'])})
        if status != 200:
            raise StopRun('PERIOD_RENAME_FAILED', (renamed or {}).get('code'))
        self.state['period'] = renamed
        self.step('label', 'DONE', period_code=self.code)

    # 8
    def check(self):
        study, model = self.state.get('study'), self.state.get('model')
        if not (study and model and self.state.get('period')):
            return self.step('check', 'PENDING')
        students = int(self.g.sql('students', p=study['period_id'])[0]['n'])
        self.step('check', 'OK', students_in_demo_period=students, model_algorithm=model['algorithm'], origin='SYNTHETIC')
        return {'period_code': self.code, 'model_algorithm': model['algorithm'], 'students_in_demo_period': students}

    def run(self):
        self.preflight()
        self.study()
        self.tutor()
        for step in (self.generate, self.importing, self.comparing, self.model, self.labeling):
            step()
        return self.check()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--operator-profile', required=True)
    parser.add_argument('--confirm-demo-target', help='Repite aquí el nombre del proyecto del destino de demostración para autorizar la escritura')
    parser.add_argument('--period-code', default=DEFAULT_CODE)
    parser.add_argument('--seed', type=int, default=1729)
    parser.add_argument('--students', type=int, help='Cantidad de estudiantes sintéticos del estudio (por defecto la del generador)')
    parser.add_argument('--repetitions', type=int, help='Repeticiones de la comparación sintética (por defecto las del sistema)')
    parser.add_argument('--tutor-id')
    parser.add_argument('--locked-tutor', action='store_true', help='Usa (o crea) la cuenta TUTOR de relleno sin acceso como tutor de la sección')
    parser.add_argument('--dry-run', action='store_true', help='Reconoce el estado de cada paso sin escribir nada')
    args = parser.parse_args(argv)
    try:
        from operator_profiles import admin_account
        from runtime_target import Target
        target = Target.load(args.target)
        if target.kind not in ('INSTALL', 'RESTORE') or target.project == 'riesgo-escolar':
            raise StopRun('DEMO_ONLY_ISOLATED_TARGET')
        if not args.dry_run and args.confirm_demo_target != target.project:
            raise StopRun('DEMO_TARGET_CONFIRMATION_REQUIRED', f'Repite con --confirm-demo-target {target.project}.', exit_code=3)
        account = admin_account(target, operator_profile=args.operator_profile)
        with DemoLive(target, account) as gateway:
            DemoRunner(gateway, period_code=args.period_code, seed=args.seed, students=args.students, repetitions=args.repetitions,
                       tutor_id=args.tutor_id, locked_tutor=args.locked_tutor, dry_run=args.dry_run).run()
    except StopRun as stop:
        print(json.dumps({'code': stop.code, **({'detail': stop.detail} if stop.detail else {})}, ensure_ascii=True, default=str))
        return stop.exit_code
    except RuntimeError as error:
        code = str(error)
        print(json.dumps({'code': code if re.fullmatch(r'[A-Z0-9_]{1,100}', code) else 'PREPARE_DEMO_PERIOD_FAILED'}))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
