"""Bloque 6: periodo «Demostración en vivo» (estudio sintético rotulado) con una pasarela simulada: sin Docker, sin red, sin datos reales."""
import base64
import contextlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infra'))
import prepare_demo_period as demo  # noqa: E402
import run_real_study as real  # noqa: E402


class FakeGateway:
    def __init__(self, tutors=('tutor-1',), head='0008_real_chain', extra_periods=()):
        self.tutors, self.head_value = tutors, head
        self.writes, self.study, self.models = [], None, []
        self.periods = [{'id': 'real-period', 'code': 'REAL-2026', 'school_year': 2026, 'start_date': '2026-01-01', 'end_date': '2026-12-31',
                         'data_origin': 'REAL', 'is_locked': False, 'version': 1}, *extra_periods]
        self.generate_payload = None

    def head(self):
        return self.head_value

    def api(self, method, path, body=None):
        if path == '/catalogs/tutors':
            return 200, [{'id': item} for item in self.tutors]
        if method == 'GET' and path == '/periods':
            return 200, [dict(item) for item in self.periods]
        if method == 'PATCH' and path.startswith('/periods/'):
            self.writes.append('rename')
            target = next(item for item in self.periods if item['id'] == path.split('/')[-1])
            assert body['expected_version'] == target['version'] and body['data_origin'] == 'SYNTHETIC' and body['creation_key']
            target.update(code=body['code'], version=target['version'] + 1)
            return 200, dict(target)
        if method == 'POST' and path.endswith('/commit'):
            self.writes.append('commit')
            self.study['bound'] = 240
            return 200, {'created_snapshots': 240}
        raise AssertionError((method, path))

    def internal(self, command, payload):
        if command == 'export-csv':
            return {'period_id': self.study['period_id'], 'csv_sha256': 'x', 'csv_base64': base64.b64encode(b'cabecera\n').decode()}
        self.writes.append('internal:' + command)
        if command == 'generate':
            self.generate_payload = payload
            self.study = {'id': 'study-1', 'period_id': 'demo-period', 'bound': 0, 'compared': False}
            self.periods.append({'id': 'demo-period', 'code': 'SYN-0123456789ab', 'school_year': 2025, 'start_date': '2025-01-01',
                                 'end_date': '2025-12-31', 'data_origin': 'SYNTHETIC', 'is_locked': False, 'version': 1})
            return {'study_id': 'study-1', 'period_id': 'demo-period'}
        if command == 'compare':
            self.study['compared'] = True
            return {'selected_algorithm': 'SVM'}
        if command == 'register':
            self.models.append({'id': 'model-1', 'algorithm': 'SVM', 'is_active': False})
            return {'model_id': 'model-1', 'algorithm': 'SVM'}
        if command == 'activate':
            self.models[0]['is_active'] = True
            return {'approval_kind': 'TECHNICAL_SIMULATION'}
        raise AssertionError(command)

    def import_csv(self, period_id, content):
        self.writes.append('preview')
        return {'id': 'batch-1', 'status': 'READY', 'preview_version': 1, 'total_rows': 240}

    def create_locked_tutor(self):
        self.writes.append('locked-tutor')
        return 'locked-1'

    def sql(self, name, **params):
        if name == 'study':
            return [dict(self.study)] if self.study else []
        if name == 'models':
            return [dict(item) for item in self.models]
        if name == 'students':
            return [{'n': 60 if self.study and self.study['bound'] else 0}]       # los estudiantes sintéticos del generador
        raise AssertionError(name)


def execute(gateway, **options):
    lines = []
    summary = demo.DemoRunner(gateway, emit=lines.append, **options).run()
    return summary, [json.loads(line) for line in lines]


def test_full_run_creates_the_labelled_demo_period_in_order_and_no_students():
    gateway = FakeGateway()
    summary, lines = execute(gateway)
    assert gateway.writes == ['internal:generate', 'preview', 'commit', 'internal:compare', 'internal:register', 'internal:activate', 'rename']
    assert {item['step']: item['status'] for item in lines} == {'preflight': 'OK', 'tutor': 'SINGLE_EXISTING', 'study': 'DONE', 'import': 'DONE',
                                                                 'compare': 'DONE', 'model': 'DONE', 'label': 'DONE', 'check': 'OK'}
    # Solo los 60 estudiantes sintéticos del generador; el de la demostración lo registra el usuario en vivo.
    assert summary == {'period_code': 'DEMO-VIVO', 'model_algorithm': 'SVM', 'students_in_demo_period': 60}
    assert next(item for item in gateway.periods if item['id'] == 'demo-period')['code'] == 'DEMO-VIVO'
    assert gateway.generate_payload['tutor_id'] == 'tutor-1' and gateway.generate_payload['seed'] == 1729
    assert next(item for item in gateway.periods if item['id'] == 'real-period')['code'] == 'REAL-2026'   # el periodo real no se toca


def test_second_run_is_idempotent_and_dry_run_writes_nothing():
    gateway = FakeGateway()
    execute(gateway)
    before = list(gateway.writes)
    _, lines = execute(gateway)
    assert gateway.writes == before
    assert {item['step']: item['status'] for item in lines if item['step'] != 'check'} == {
        'preflight': 'OK', 'study': 'REUSED', 'tutor': 'NOT_NEEDED', 'import': 'REUSED', 'compare': 'REUSED', 'model': 'REUSED', 'label': 'REUSED'}
    fresh = FakeGateway()
    summary, lines = execute(fresh, dry_run=True)
    assert fresh.writes == [] and summary is None
    assert {item['step']: item['status'] for item in lines}['study'] == 'PENDING'


def test_the_tutor_is_never_chosen_among_several_and_the_placeholder_is_explicit():
    with pytest.raises(real.StopRun) as error:
        execute(FakeGateway(tutors=()))
    assert error.value.code == 'TUTOR_REQUIRED'
    with pytest.raises(real.StopRun) as error:
        execute(FakeGateway(tutors=('a', 'b')))
    assert error.value.code == 'TUTOR_CHOICE_REQUIRED'
    locked = FakeGateway(tutors=('real-tutor',))
    execute(locked, locked_tutor=True)
    assert locked.writes.count('locked-tutor') == 1 and locked.generate_payload['tutor_id'] == 'locked-1'
    explicit = FakeGateway(tutors=('a', 'b'))
    execute(explicit, tutor_id='b')
    assert explicit.generate_payload['tutor_id'] == 'b' and 'locked-tutor' not in explicit.writes


def test_preconditions_head_code_and_collision():
    with pytest.raises(real.StopRun) as error:
        execute(FakeGateway(head='0007_real_protocol'))
    assert error.value.code == 'TARGET_NOT_AT_0008'
    with pytest.raises(real.StopRun) as error:
        execute(FakeGateway(), period_code='demo vivo')
    assert error.value.code == 'PERIOD_CODE_INVALID'
    clash = FakeGateway(extra_periods=({'id': 'other', 'code': 'DEMO-VIVO', 'school_year': 2024, 'start_date': '2024-01-01',
                                        'end_date': '2024-12-31', 'data_origin': 'SYNTHETIC', 'is_locked': False, 'version': 1},))
    with pytest.raises(real.StopRun) as error:
        execute(clash)
    assert error.value.code == 'PERIOD_CODE_IN_USE'


def patch_main(monkeypatch, gateway, *, kind='INSTALL', project='s6-install-0123456789ab'):
    import runtime_target
    monkeypatch.setattr(runtime_target.Target, 'load', classmethod(lambda cls, path: SimpleNamespace(kind=kind, project=project)))
    monkeypatch.setattr('operator_profiles.admin_account', lambda *a, **k: {'email': 'admin@example.test', 'password': 'x'})
    monkeypatch.setattr(demo, 'DemoLive', lambda target, account: contextlib.nullcontext(gateway))


def test_the_active_installation_is_never_a_target_and_writing_needs_the_project_name(monkeypatch, capsys, tmp_path):
    arguments = ['--target', str(tmp_path / 'destino.json'), '--operator-profile', 'x', '--locked-tutor']
    gateway = FakeGateway()
    patch_main(monkeypatch, gateway, kind='ACTIVE', project='riesgo-escolar')
    assert demo.main(arguments + ['--confirm-demo-target', 'riesgo-escolar']) == 2
    assert json.loads(capsys.readouterr().out)['code'] == 'DEMO_ONLY_ISOLATED_TARGET' and gateway.writes == []
    assert demo.main(arguments + ['--dry-run']) == 2                                          # ni siquiera en simulacro
    assert json.loads(capsys.readouterr().out)['code'] == 'DEMO_ONLY_ISOLATED_TARGET'
    patch_main(monkeypatch, gateway)
    assert demo.main(arguments) == 3                                                         # sin confirmar el proyecto no escribe
    assert json.loads(capsys.readouterr().out)['code'] == 'DEMO_TARGET_CONFIRMATION_REQUIRED' and gateway.writes == []
    assert demo.main(arguments + ['--confirm-demo-target', 'otro-proyecto']) == 3
    capsys.readouterr()
    assert demo.main(arguments + ['--dry-run']) == 0 and gateway.writes == []                # el simulacro no pide confirmación
    capsys.readouterr()
    assert demo.main(arguments + ['--confirm-demo-target', 's6-install-0123456789ab']) == 0
    assert 'internal:generate' in gateway.writes and 'DEMO-VIVO' in capsys.readouterr().out


def test_output_has_no_student_data_and_no_password_option():
    _, lines = execute(FakeGateway())
    text = json.dumps(lines)
    assert 'student_code' not in text and 'full_name' not in text
    source = Path(demo.__file__).read_text(encoding='utf-8')
    assert "'--password'" not in source and 'getpass' not in source


def test_summary_comparison_reports_identity_and_the_paths_that_differ(tmp_path, capsys):
    import compare_real_summaries as compare
    reference = {'counts': {'students': 60}, 'models': {'RF': {'accuracy': {'mean': 0.8625, 'sd': 0.014}}}, 'rows': [1, 2, 3]}
    first, second, third = (tmp_path / name for name in ('a.json', 'b.json', 'c.json'))
    first.write_text(json.dumps(reference), encoding='utf-8')
    second.write_text(json.dumps(reference), encoding='utf-8')
    third.write_text(json.dumps({**reference, 'counts': {'students': 61}, 'rows': [1, 2], 'extra': True}), encoding='utf-8')
    assert compare.main([str(first), str(second)]) == 0 and capsys.readouterr().out.strip() == 'IDENTICOS'
    assert compare.main([str(first), str(third)]) == 1
    out = capsys.readouterr().out
    assert '$.counts.students' in out and '$.rows[len]' in out and '$.extra' in out and 'AUSENTE' in out
    assert compare.main([str(first), str(tmp_path / 'no-existe.json')]) == 2
    assert compare.differences({'a': 1}, {'a': 1.0})                                      # 1 y 1.0 no son «idénticos» (el tipo también cuenta)
