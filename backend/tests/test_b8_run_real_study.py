"""Bloque 5 (A/E): orquestador de la corrida REAL con una pasarela simulada (sin Docker, sin red) y entradas FICTICIAS.

Las entradas salen del conversor real aplicado al libro ficticio de las pruebas del Bloque 4: así los CSV, el resumen y los hashes son coherentes.
"""
import contextlib
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
import convert_real_excel as converter  # noqa: E402
import run_real_study as runner  # noqa: E402
from test_b6_convert_excel import fictitious_sheets, write_book, NAME_WORDS  # noqa: E402

LEVELS = ('LOW', 'MEDIUM', 'HIGH')


def fake_scope(mean, at_risk):
    spread = lambda value: {'mean': value, 'sd': 0.02, 'minimum': value - 0.03, 'maximum': value + 0.03, 'reason': None}
    return {'repetitions': 20, 'reference_at_risk_per_repetition': at_risk, 'detection': spread(mean), 'medium_detected': spread(mean - 0.1),
            'high_detected': spread(min(mean + 0.05, 1.0)), 'high_as_low': spread(0.0), 'low_flagged': spread(0.1),
            'pooled': {'reference_at_risk': 20 * at_risk, 'detected': round(mean * at_risk * 20), 'reference_low': 800, 'low_flagged': 80,
                       'reference_medium': 640, 'medium_flagged': 500, 'reference_high': 960, 'high_flagged': 960, 'high_as_low': 0}}


def fake_detection(base):
    return {'definition': 'OUT_OF_FOLD_MEDIUM_OR_HIGH_V1', 'metric_basis': 'OUT_OF_FOLD', 'note': 'nota', 'total': fake_scope(base, 80),
            'by_bimester': {'B1': fake_scope(base - 0.01, 45), 'B2': fake_scope(base + 0.01, 35)}}


def fake_report():
    spread = lambda mean: {'mean': mean, 'sd': 0.01, 'minimum': mean - 0.02, 'maximum': mean + 0.02, 'reason': None}
    algorithms = {}
    for index, name in enumerate(('DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST')):
        base = 0.4 + 0.1 * index
        algorithms[name] = {'repeated_cv': {'repetitions': 20, 'accuracy': spread(base), 'balanced_accuracy': spread(base), 'cohen_kappa': spread(base - 0.1),
            'macro': {'precision': spread(base), 'recall': spread(base), 'f1': spread(base)}, 'class_order': list(LEVELS),
            'per_class': {level: {'precision': spread(base), 'recall': spread(base), 'f1': spread(base), 'support_per_repetition': 40}
                          for level in LEVELS},
            'aggregated_confusion_matrix': [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
            'detection': fake_detection(0.5 + base / 2 if name != 'DUMMY' else 1.0),
            'leave_one_student_out': {'accuracy': base, 'macro': {'f1': base}, 'per_class': {'HIGH': {'recall': base}}}}
    return {'selected_algorithm': 'XGBOOST', 'selection_rule': 'REPEATED_CV_MACRO_F1_THEN_BALANCED_ACCURACY_THEN_FIXED_ORDER', 'repetitions': 20,
            'requested_folds': 5, 'students': 60, 'observations': 120, 'support_by_class': {}, 'warnings': ['n = 60 estudiantes: resultados exploratorios'],
            'approval_kind': 'LOCAL_EXPLORATORY', 'seed': 0, 'algorithms': algorithms}


class FakeGateway:
    def __init__(self, inputs, head='0008_real_chain', tutors=('tutor-1',), distribution=None, sql_pder=None, no_detection=False):
        self.inputs, self.head_value, self.tutors, self.no_detection = inputs, head, tutors, no_detection
        self.distribution = distribution or inputs.expected_levels
        self.sql_pder = sql_pder
        self.writes, self.s = [], dict(period=None, sections=[], protocol=None, study=False, imported=False, refs=False, compared=False,
                                      model=None, predictions={})

    def head(self):
        return self.head_value

    def write(self, what):
        self.writes.append(what)

    def api(self, method, path, body=None):
        s = self.s
        if method == 'GET' and path == '/periods':
            return 200, [s['period']] if s['period'] else []
        if method == 'POST' and path == '/periods':
            self.write('period'); s['period'] = {'id': 'period-1', 'code': body['code'], 'data_origin': 'REAL', 'school_year': body['school_year']}
            return 200, s['period']
        if method == 'GET' and path.startswith('/sections'):
            return 200, s['sections']
        if method == 'POST' and path == '/sections':
            self.write('section'); s['sections'].append({'id': 'sec-' + body['code'], 'code': body['code'], 'grade': body['grade'],
                                                         'tutor_id': body['tutor_id']})
            return 200, s['sections'][-1]
        if path == '/catalogs/tutors':
            return 200, [{'id': item} for item in self.tutors]
        if method == 'GET' and path.startswith('/processing-protocols'):
            return (200, s['protocol']) if s['protocol'] else (404, {'code': 'PROTOCOL_NOT_FOUND'})
        if method == 'POST' and path == '/processing-protocols':
            self.write('protocol'); s['protocol'] = {**body, 'id': 'protocol-1', 'authorization_confirmed_by_admin': False,
                                                     'bimesters': body['bimesters'], 'grade_scale_max': '20.00'}
            return 200, s['protocol']
        if path.endswith('/confirm'):
            self.write('confirm'); s['protocol']['authorization_confirmed_by_admin'] = True
            return 200, s['protocol']
        if path.startswith('/imports/') and path.endswith('/commit'):
            self.write('commit'); s['imported'] = True
            return 200, {'created_snapshots': len(self.inputs.cut_rows)}
        if method == 'POST' and path == '/predictions/run':
            self.write('run:' + body['as_of'][:10])
            bimester = next(b for b, item in self.inputs.calendar.items() if item['cutoff_at'] == body['as_of'])
            close = self.inputs.calendar[bimester]['close'].isoformat()
            s['predictions'][close] = self.inputs.calendar[bimester]['rows']
            return 200, {'selected': 60, 'created': 60, 'reused': 0, 'abstentions': [],
                         'followup': {'created': 46, 'updated': 0, 'retained_low': 0, 'no_alert': 14}}
        if path.startswith('/indicators?'):
            bimester = path.split('bimester=')[1]
            numerator, denominator = self.pder(bimester)
            scope = fake_report()['algorithms']['XGBOOST']['detection']['by_bimester'][bimester]
            shown = None if self.no_detection else {'bimester': bimester, 'repetitions': 20, 'metric_basis': 'OUT_OF_FOLD', 'pooled': scope['pooled'],
                                                    'detection': {'mean': 100 * scope['detection']['mean'], 'sd': 100 * scope['detection']['sd']}}
            return 200, {'retrospective_alerts': 51, 'prv': {'percent': 100.0, 'received': 120, 'reason': None},
                         'total': {'eligible_students': 60, 'pder': {'numerator': numerator, 'denominator': denominator},
                                   'cra': {'numerator': 60, 'denominator': 60}, 'nia': {'mean': None, 'reason': 'NO_REAL_INTERVENTIONS'},
                                   'opportune': {'percent': None, 'reason': 'NO_REAL_INTERVENTIONS'}, 'metric_basis': 'OUT_OF_FOLD',
                                   'validated_detection': shown, 'validated_detection_reason': 'NO_OUT_OF_SAMPLE_REPORT' if shown is None else None}}
        raise AssertionError((method, path))

    def pder(self, bimester):
        return (46, 46)

    def raw_get(self, path):
        return ('origen,codigo_anonimo\nREAL,' + self.inputs.codes[0] + '\n').encode()

    def import_csv(self, period_id, content):
        self.write('preview')
        return {'id': 'batch-1', 'status': 'READY', 'data_origin': 'REAL', 'preview_version': 1, 'total_rows': len(self.inputs.cut_rows)}

    def internal(self, command, payload):
        s = self.s
        self.write('internal:' + command)
        if command == 'register-study':
            s['study'] = True
            return {'study_id': 'study-1', 'rows': len(self.inputs.cut_rows), 'students': len(self.inputs.codes), 'horizon_days': 17}
        if command == 'compare':
            s['compared'] = True
            return {}
        if command == 'register':
            s['model'] = {'id': 'model-1', 'algorithm': 'XGBOOST', 'is_active': False, 'approval_kind': 'LOCAL_EXPLORATORY'}
            return {'model_id': 'model-1', 'algorithm': 'XGBOOST'}
        if command == 'activate':
            s['model']['is_active'] = True
            return {'approval_kind': 'LOCAL_EXPLORATORY'}
        raise AssertionError(command)

    def create_locked_tutor(self):
        self.write('locked-tutor')
        return 'locked-1'

    def load_closings(self, period_id, rows):
        self.write('closings'); self.s['refs'] = True
        return {'created': len(rows), 'reused': 0}

    def sql(self, name, **params):
        s, inputs = self.s, self.inputs
        if name == 'study':
            return [{'id': 'study-1', 'compared': s['compared']}] if s['study'] else []
        if name == 'batches':
            return [{'n': 1 if s['imported'] else 0}]
        if name == 'references':
            return [{'n': len(inputs.close_rows) if s['refs'] else 0}]
        if name == 'counts':
            return [{'students': len(inputs.codes), 'snapshots': len(inputs.cut_rows), 'risk_references': len(inputs.close_rows), 'eligible': len(inputs.codes)}]
        if name == 'distribution':
            return [{'bimester': b, 'risk_level': level, 'n': n} for b, counts in self.distribution.items() for level, n in counts.items()]
        if name == 'comparison':
            return [{'report': fake_report()}]
        if name == 'models':
            return [s['model']] if s['model'] else []
        if name == 'predictions':
            return [{'n': s['predictions'].get(params['close'], 0)}]
        if name == 'clocks':
            return [{'predictions': 120, 'simulated_predictions': 120, 'alerts': 51, 'simulated_alerts': 51}]
        if name == 'pder':
            numerator, denominator = self.sql_pder or (46, 46)
            return [{'numerator': numerator, 'denominator': denominator}]
        if name == 'cra':
            return [{'numerator': 60, 'denominator': 60}]
        if name == 'matrix':
            return [{'reference': level, 'predicted': level, 'n': 20} for level in LEVELS]
        raise AssertionError(name)


@pytest.fixture
def folder(tmp_path):
    sheets, names = fictitious_sheets(anomalies=converter.CAUSES)
    book = write_book(tmp_path / 'ficticio.xlsx', sheets)
    out = tmp_path / 'entrada'
    converter.convert(book, out)
    return out


def execute(folder, tmp_path, gateway=None, **options):
    lines = []
    inputs = runner.Inputs(folder)
    gateway = gateway or FakeGateway(inputs)
    results = tmp_path / 'resultados'
    summary = runner.Runner(gateway, inputs, results, emit=lines.append, **options).run()
    return gateway, summary, lines, results


def files(results):
    return sorted(item.name for item in results.iterdir()) if results.exists() else []


def test_full_run_executes_every_step_and_writes_results_outside_the_input(folder, tmp_path):
    gateway, summary, lines, results = execute(folder, tmp_path, confirm_protocol=True)
    statuses = {json.loads(line)['step']: json.loads(line)['status'] for line in lines}
    assert statuses == {'preflight': 'OK', 'period': 'DONE', 'sections': 'DONE', 'protocol': 'DONE', 'study': 'DONE', 'import': 'DONE',
                        'closings': 'DONE', 'checks': 'OK', 'comparison': 'DONE', 'model': 'DONE', 'evaluation': 'DONE', 'indicators': 'DONE'}
    assert gateway.writes == ['period', 'section', 'section', 'protocol', 'confirm', 'internal:register-study', 'preview', 'commit', 'closings',
                              'internal:compare', 'internal:register', 'internal:activate', 'run:2026-04-21', 'run:2026-06-30']
    assert files(results) == ['comparacion_modelos_completa.json', 'indicadores_B1.json', 'indicadores_B1_alumnos.csv',
                              'indicadores_B1_intervenciones.csv', 'indicadores_B2.json', 'indicadores_B2_alumnos.csv',
                              'indicadores_B2_intervenciones.csv', 'resumen_agregado.json']
    assert summary['comparison']['models']['XGBOOST']['cohen_kappa']['mean'] is not None
    assert summary['indicators']['B1']['agree'] and summary['indicators']['B2']['agree']
    assert summary['unavailable']['NIA'] == 'NO_REAL_INTERVENTIONS' and 'no mide impacto del sistema' in summary['reading']
    # Bloque 5.1: detección validada del modelo activo (total y por bimestre), contrastada con lo que devuelve la API (lo que ve la pantalla).
    validated = summary['validated_detection']
    assert validated['model'] == 'XGBOOST' and set(validated) >= {'total', 'B1', 'B2'}
    assert validated['total']['detection']['mean'] == pytest.approx(0.85) and validated['total']['detection']['sd'] == pytest.approx(0.02)
    assert validated['B1']['pooled']['reference_at_risk'] == 20 * 45 and validated['B2']['pooled']['reference_at_risk'] == 20 * 35
    assert all(summary['indicators'][b]['validated_detection']['agrees_with_report'] and summary['indicators'][b]['validated_detection']['metric_basis'] == 'OUT_OF_FOLD'
               for b in ('B1', 'B2'))
    assert summary['comparison']['models']['DUMMY']['detection']['total']['detection']['mean'] == 1.0          # el modelo que marca a todos detecta todo
    assert summary['comparison']['models']['DUMMY']['detection']['total']['low_flagged']['mean'] > 0
    notes = summary['reading_notes']
    assert 'en muestra' in notes['pder_in_sample'] and 'no pierde casos' in notes['cra'] and 'No es un resultado de desempeño' in notes['cra']


def test_second_run_is_idempotent_and_writes_nothing(folder, tmp_path):
    gateway, _, _, _ = execute(folder, tmp_path, confirm_protocol=True)
    before = list(gateway.writes)
    _, _, lines, _ = execute(folder, tmp_path, gateway=gateway, confirm_protocol=True)
    assert gateway.writes == before
    statuses = {json.loads(line)['step']: json.loads(line)['status'] for line in lines}
    assert all(status in ('REUSED', 'OK') for step, status in statuses.items() if step != 'indicators')
    assert statuses['evaluation'] == 'REUSED' and statuses['model'] == 'REUSED' and statuses['comparison'] == 'REUSED'


def test_dry_run_writes_nothing_anywhere(folder, tmp_path):
    gateway, summary, lines, results = execute(folder, tmp_path, dry_run=True, confirm_protocol=True)
    assert gateway.writes == [] and summary is None and files(results) == []
    statuses = {json.loads(line)['step']: json.loads(line)['status'] for line in lines}
    assert statuses['preflight'] == 'OK' and statuses['period'] == 'PENDING' and statuses['indicators'] == 'PENDING'


def test_a_different_input_hash_stops_before_anything(folder, tmp_path):
    (folder / 'cortes.csv').write_bytes((folder / 'cortes.csv').read_bytes() + b'\n')
    with pytest.raises(runner.StopRun) as error:
        runner.Inputs(folder)
    assert error.value.code == 'INPUT_HASH_MISMATCH' and error.value.detail == 'cortes.csv'


def test_a_different_risk_distribution_stops_before_the_comparison(folder, tmp_path):
    inputs = runner.Inputs(folder)
    wrong = {b: dict(counts) for b, counts in inputs.expected_levels.items()}
    wrong['B1']['LOW'] += 1
    wrong['B1']['HIGH'] -= 1
    gateway = FakeGateway(inputs, distribution=wrong)
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=gateway, confirm_protocol=True)
    assert error.value.code == 'REFERENCE_DISTRIBUTION_MISMATCH'
    assert 'internal:compare' not in gateway.writes and not any(item.startswith('run:') for item in gateway.writes)


def test_protocol_is_never_confirmed_without_the_explicit_flag(folder, tmp_path):
    inputs = runner.Inputs(folder)
    gateway = FakeGateway(inputs)
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=gateway)
    assert error.value.code == 'PROTOCOL_CONFIRMATION_REQUIRED' and error.value.exit_code == 3
    assert 'confirm' not in gateway.writes and 'internal:register-study' not in gateway.writes


def test_preconditions_tutor_and_migration(folder, tmp_path):
    inputs = runner.Inputs(folder)
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=FakeGateway(inputs, tutors=()), confirm_protocol=True)
    assert error.value.code == 'TUTOR_REQUIRED'
    gateway = FakeGateway(inputs, tutors=())                                   # con --locked-tutor se crea el relleno sin acceso
    execute(folder, tmp_path, gateway=gateway, confirm_protocol=True, locked_tutor=True)
    assert gateway.writes.count('locked-tutor') == 1 and gateway.writes.count('section') == 2
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=FakeGateway(inputs, head='0007_real_protocol'), confirm_protocol=True)
    assert error.value.code == 'TARGET_NOT_AT_0008'
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=FakeGateway(inputs, tutors=('a', 'b')), confirm_protocol=True)
    assert error.value.code == 'TUTOR_CHOICE_REQUIRED'


def test_results_and_input_inside_git_are_rejected(folder, tmp_path, capsys):
    repository = tmp_path / 'repo'
    (repository / '.git').mkdir(parents=True)
    arguments = ['--target', str(tmp_path / 'destino.json'), '--operator-profile', 'x', '--input', str(folder), '--results', str(repository / 'res')]
    assert runner.main(arguments) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'RESULTS_INSIDE_GIT' and not (repository / 'res').exists()
    inside = repository / 'entrada'
    inside.mkdir()
    for item in folder.iterdir():
        (inside / item.name).write_bytes(item.read_bytes())
    assert runner.main(['--target', str(tmp_path / 'destino.json'), '--operator-profile', 'x', '--input', str(inside),
                        '--results', str(tmp_path / 'fuera')]) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'INPUT_INSIDE_GIT'


def test_outputs_have_no_student_codes_or_names_except_the_per_student_csv(folder, tmp_path):
    gateway, summary, lines, results = execute(folder, tmp_path, confirm_protocol=True)
    codes = runner.Inputs(folder).codes
    public = ''.join(lines) + (results / 'resumen_agregado.json').read_text(encoding='utf-8') + (results / 'comparacion_modelos_completa.json').read_text(encoding='utf-8')
    public += ''.join((results / f'indicadores_{b}.json').read_text(encoding='utf-8') for b in ('B1', 'B2'))
    assert not any(code in public for code in codes) and not any(word in public for word in NAME_WORDS)
    assert any(code in (results / 'indicadores_B1_alumnos.csv').read_text(encoding='utf-8') for code in codes)      # solo este archivo lleva códigos


def test_sql_verification_reports_disagreement_instead_of_hiding_it(folder, tmp_path):
    inputs = runner.Inputs(folder)
    _, summary, _, _ = execute(folder, tmp_path, gateway=FakeGateway(inputs, sql_pder=(45, 46)), confirm_protocol=True)
    assert summary['indicators']['B1']['agree'] is False and summary['indicators']['B1']['sql']['pder'] == [45, 46]


def test_aggregate_refuses_to_contain_student_codes(folder, tmp_path, monkeypatch):
    inputs = runner.Inputs(folder)
    monkeypatch.setattr(runner, 'model_table', lambda report: {'XGBOOST': {'leak': inputs.codes[0]}})
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=FakeGateway(inputs), confirm_protocol=True)
    assert error.value.code == 'AGGREGATE_CONTAINS_STUDENT_CODES'


def test_protocol_is_derived_from_the_files_and_the_cli_has_no_password_option(folder):
    inputs = runner.Inputs(folder)
    body = inputs.protocol('period-1')
    assert [item['code'] for item in body['bimesters']] == ['B1', 'B2'] and body['participation_max'] == 5
    assert [item['cutoff_available_at'][:10] for item in body['bimesters']] == ['2026-04-21', '2026-06-30']
    assert [item['cutoff_date'] for item in body['bimesters']] == ['2026-04-17', '2026-06-26']
    assert body['opportune_windows'] == {'detection_days': 0, 'intervention_days': 14} and set(body['risk_rule']) == {'version'}
    assert not {'consent', 'document', 'authorizer'} & {key for key in body}
    source = (Path(runner.__file__)).read_text(encoding='utf-8')
    assert "'--password'" not in source and 'getpass' not in source


# ---------------------------------------------------------------- instalación activa (carga REAL con confirmación explícita y respaldo previo)
def pre_backup_manifest(**changes):
    manifest = {'id': 's6-20261018T071049Z-prueba', 'migration': '0008_real_chain', 'origin': 'SYNTHETIC', 'source': {'project': 'riesgo-escolar'},
                'created_at': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
    return {**manifest, **changes}


def test_active_target_decides_the_tutor_before_writing_anything(folder, tmp_path):
    inputs = runner.Inputs(folder)
    gateway = FakeGateway(inputs, tutors=('tutor-1',))                              # un único tutor existente: fuera de la activa se elegiría solo
    with pytest.raises(runner.StopRun) as error:
        execute(folder, tmp_path, gateway=gateway, confirm_protocol=True, active=True)
    assert error.value.code == 'ACTIVE_TUTOR_EXPLICIT_REQUIRED' and gateway.writes == []
    with pytest.raises(runner.StopRun) as error:                                    # un solo tutor indicado no basta para dos secciones
        execute(folder, tmp_path, gateway=FakeGateway(inputs), confirm_protocol=True, active=True, tutors=('tutor-a', None))
    assert error.value.code == 'ACTIVE_TUTOR_EXPLICIT_REQUIRED'
    off_active = FakeGateway(inputs, tutors=('tutor-1',))                           # el comportamiento fuera de la activa no cambia
    execute(folder, tmp_path, gateway=off_active, confirm_protocol=True)
    assert {item['tutor_id'] for item in off_active.s['sections']} == {'tutor-1'}


def test_active_target_uses_the_locked_placeholder_or_the_tutors_given(folder, tmp_path):
    inputs = runner.Inputs(folder)
    locked = FakeGateway(inputs, tutors=('tutor-1',))                               # existe un tutor real, pero no se le asignan los datos REAL
    execute(folder, tmp_path, gateway=locked, confirm_protocol=True, active=True, locked_tutor=True)
    assert locked.writes.count('locked-tutor') == 1 and {item['tutor_id'] for item in locked.s['sections']} == {'locked-1'}
    explicit = FakeGateway(inputs, tutors=('tutor-1',))
    execute(folder, tmp_path, gateway=explicit, confirm_protocol=True, active=True, tutors=('tutor-a', 'tutor-b'))
    assert 'locked-tutor' not in explicit.writes
    assert [item['tutor_id'] for item in explicit.s['sections']] == ['tutor-a', 'tutor-b']


def test_active_dry_run_reports_the_missing_tutor_decision_without_writing(folder, tmp_path):
    inputs = runner.Inputs(folder)
    gateway = FakeGateway(inputs, tutors=('tutor-1',))
    gateway.s['period'] = {'id': 'period-1', 'code': 'REAL-2026', 'data_origin': 'REAL', 'school_year': 2026}
    _, summary, lines, _ = execute(folder, tmp_path, gateway=gateway, dry_run=True, confirm_protocol=True, active=True)
    assert gateway.writes == [] and summary is None
    sections = next(json.loads(line) for line in lines if json.loads(line)['step'] == 'sections')
    assert sections['status'] == 'PENDING' and sections['tutor'] == 'EXPLICIT_REQUIRED'


def test_dry_run_with_locked_tutor_and_no_tutors_is_pending_not_an_error(folder, tmp_path):
    inputs = runner.Inputs(folder)
    gateway = FakeGateway(inputs, tutors=())
    gateway.s['period'] = {'id': 'period-1', 'code': 'REAL-2026', 'data_origin': 'REAL', 'school_year': 2026}
    _, _, lines, _ = execute(folder, tmp_path, gateway=gateway, dry_run=True, confirm_protocol=True, locked_tutor=True)
    sections = next(json.loads(line) for line in lines if json.loads(line)['step'] == 'sections')
    assert gateway.writes == [] and sections['status'] == 'PENDING' and sections['tutor'] == 'LOCKED_PLACEHOLDER'


def test_pre_backup_must_be_this_installation_at_0008_and_recent():
    now = datetime.now(timezone.utc)
    assert runner.check_pre_backup(pre_backup_manifest(), 'riesgo-escolar') == 's6-20261018T071049Z-prueba'
    cases = (({'source': {'project': 's6-install-0fe58a34e54f'}}, 'PRE_BACKUP_OTHER_INSTALLATION'),
             ({'migration': '0004_followup'}, 'PRE_BACKUP_NOT_AT_0008'),
             ({'created_at': (now - timedelta(hours=25)).isoformat()}, 'PRE_BACKUP_TOO_OLD'),
             ({'created_at': (now + timedelta(hours=2)).isoformat()}, 'PRE_BACKUP_TOO_OLD'),
             ({'created_at': now.replace(tzinfo=None).isoformat()}, 'PRE_BACKUP_DATE_INVALID'),
             ({'created_at': 'ayer'}, 'PRE_BACKUP_DATE_INVALID'))
    for change, code in cases:
        with pytest.raises(runner.StopRun) as error:
            runner.check_pre_backup(pre_backup_manifest(**change), 'riesgo-escolar')
        assert error.value.code == code, change


def test_active_confirmation_and_pre_backup_are_required_before_touching_credentials_or_the_server(folder, tmp_path, monkeypatch, capsys):
    import runtime_target
    monkeypatch.setattr(runtime_target.Target, 'load', classmethod(lambda cls, path: SimpleNamespace(kind='ACTIVE', project='riesgo-escolar')))
    monkeypatch.setattr(runner, 'Live', lambda *a, **k: pytest.fail('La activa no debe abrirse sin confirmación y respaldo'))
    monkeypatch.setattr('operator_profiles.admin_account', lambda *a, **k: pytest.fail('No se leen credenciales antes de las protecciones'))
    base = ['--target', str(tmp_path / 'activa.json'), '--operator-profile', 'x', '--input', str(folder), '--results', str(tmp_path / 'res'),
            '--confirm-protocol', '--locked-tutor']
    assert runner.main(base) == 3
    assert json.loads(capsys.readouterr().out)['code'] == 'ACTIVE_CONFIRMATION_REQUIRED'
    assert runner.main(base + ['--confirm-active', 'otro-proyecto', '--pre-backup', str(tmp_path / 'r.sebackup')]) == 3
    assert json.loads(capsys.readouterr().out)['code'] == 'ACTIVE_CONFIRMATION_REQUIRED'
    assert runner.main(base + ['--confirm-active', 'riesgo-escolar']) == 3
    assert json.loads(capsys.readouterr().out)['code'] == 'PRE_BACKUP_REQUIRED'
    monkeypatch.setattr(runner, 'load_pre_backup', lambda path: pre_backup_manifest(migration='0004_followup'))
    assert runner.main(base + ['--confirm-active', 'riesgo-escolar', '--pre-backup', str(tmp_path / 'r.sebackup')]) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'PRE_BACKUP_NOT_AT_0008' and not (tmp_path / 'res').exists()


def test_active_run_goes_ahead_with_confirmation_and_backup_and_reports_the_backup_without_paths(folder, tmp_path, monkeypatch, capsys):
    import runtime_target
    inputs = runner.Inputs(folder)
    gateway = FakeGateway(inputs, tutors=('tutor-1',))
    monkeypatch.setattr(runtime_target.Target, 'load', classmethod(lambda cls, path: SimpleNamespace(kind='ACTIVE', project='riesgo-escolar')))
    monkeypatch.setattr('operator_profiles.admin_account', lambda *a, **k: {'email': 'admin@example.test', 'password': 'x'})
    monkeypatch.setattr(runner, 'Live', lambda target, account: contextlib.nullcontext(gateway))
    monkeypatch.setattr(runner, 'load_pre_backup', lambda path: pre_backup_manifest())
    secret_name = 'respaldo-privado-no-debe-aparecer.sebackup'
    code = runner.main(['--target', str(tmp_path / 'activa.json'), '--operator-profile', 'x', '--input', str(folder), '--results', str(tmp_path / 'res'),
                        '--confirm-protocol', '--locked-tutor', '--confirm-active', 'riesgo-escolar', '--pre-backup', str(tmp_path / secret_name)])
    output = capsys.readouterr().out
    guard = json.loads(output.splitlines()[0])
    assert code == 0 and guard == {'step': 'active_guard', 'status': 'OK', 'pre_backup_id': 's6-20261018T071049Z-prueba', 'pre_backup_origin': 'SYNTHETIC'}
    assert secret_name not in output and 'locked-tutor' in gateway.writes
    assert {item['tutor_id'] for item in gateway.s['sections']} == {'locked-1'}


def test_dry_run_on_the_active_target_does_not_require_confirmation_or_backup(folder, tmp_path, monkeypatch, capsys):
    import runtime_target
    inputs = runner.Inputs(folder)
    gateway = FakeGateway(inputs, tutors=('tutor-1',))
    monkeypatch.setattr(runtime_target.Target, 'load', classmethod(lambda cls, path: SimpleNamespace(kind='ACTIVE', project='riesgo-escolar')))
    monkeypatch.setattr('operator_profiles.admin_account', lambda *a, **k: {'email': 'admin@example.test', 'password': 'x'})
    monkeypatch.setattr(runner, 'Live', lambda target, account: contextlib.nullcontext(gateway))
    monkeypatch.setattr(runner, 'load_pre_backup', lambda path: pytest.fail('El simulacro no pide respaldo'))
    assert runner.main(['--target', str(tmp_path / 'activa.json'), '--operator-profile', 'x', '--input', str(folder), '--results', str(tmp_path / 'res'),
                        '--dry-run']) == 0
    assert gateway.writes == [] and 'active_guard' not in capsys.readouterr().out


def test_missing_detection_in_the_api_is_recorded_as_such_not_filled(folder, tmp_path):
    inputs = runner.Inputs(folder)
    _, summary, _, _ = execute(folder, tmp_path, gateway=FakeGateway(inputs, no_detection=True), confirm_protocol=True)
    assert summary['indicators']['B1']['validated_detection'] == {'value': None, 'reason': 'NO_OUT_OF_SAMPLE_REPORT'}
