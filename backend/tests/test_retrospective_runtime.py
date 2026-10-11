"""Fail closed at the interpreter boundary and run the real compatible worker."""
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest

from app.ml.retrospective import FEATURES, MODEL_SHA256, RetrospectiveError
from app.ml.retrospective_runtime import REFERENCE_VERSIONS, invoke, evaluate_reference, partial_reference


def test_missing_reference_never_falls_back(monkeypatch):
    monkeypatch.setenv('RETROSPECTIVE_PYTHON', '/missing/reference/python')
    monkeypatch.setattr('joblib.load', lambda *a, **k: pytest.fail('Parent must never load'))
    with pytest.raises(RetrospectiveError, match='REFERENCE_RUNTIME_UNAVAILABLE'):
        invoke('probe')


def test_untrusted_package_rejected_before_process(monkeypatch):
    import sys
    monkeypatch.setenv('RETROSPECTIVE_PYTHON', sys.executable)
    monkeypatch.setattr('subprocess.run', lambda *a, **k: pytest.fail('Untrusted bytes must not reach worker'))
    with pytest.raises(RetrospectiveError, match='UNTRUSTED_PACKAGE'):
        invoke('inspect', b'wrong')


def test_worker_versions_are_verified_and_environment_is_clean(monkeypatch):
    import json, sys
    monkeypatch.setenv('RETROSPECTIVE_PYTHON', sys.executable)
    monkeypatch.setenv('DATABASE_URL', 'must-not-leave-parent')
    def fake_run(command, **kwargs):
        assert command[1] == '-I'
        assert 'DATABASE_URL' not in kwargs['env'] and 'PYTHONPATH' not in kwargs['env']
        assert kwargs['timeout'] == 30
        return SimpleNamespace(returncode=0, stderr='', stdout=json.dumps({'versions': {**REFERENCE_VERSIONS, 'numpy': 'different'},
            'model_sha256': MODEL_SHA256, 'result': {}}))
    monkeypatch.setattr('subprocess.run', fake_run)
    with pytest.raises(RetrospectiveError, match='REFERENCE_VERSION_MISMATCH'):
        invoke('probe')


@pytest.mark.skipif(os.name == 'nt', reason='Reference interpreter boundary targets Linux Docker')
def test_incompatible_interpreter_rejected_before_joblib(monkeypatch):
    import sys
    monkeypatch.setenv('RETROSPECTIVE_PYTHON', sys.executable)
    with pytest.raises(RetrospectiveError, match='REFERENCE_VERSION_MISMATCH'):
        invoke('probe')


def test_real_reference_runtime_no_fit_matches_b2(monkeypatch):
    executable = Path(os.environ.get('RETROSPECTIVE_PYTHON', '/opt/retrospective/bin/python3.12'))
    package = os.environ.get('RETROSPECTIVE_TEST_ZIP')
    if not executable.is_file() or not package:
        pytest.skip('Run in Docker tester with reference runtime and authorized ZIP')
    # Parent backend estimator must never deserialize the real artefact.
    monkeypatch.setattr('joblib.load', lambda *a, **k: pytest.fail('Wrong interpreter'))
    probe = invoke('probe')
    assert probe['versions'] == REFERENCE_VERSIONS and probe['isolated']
    assert probe['prefix'] == '/opt/retrospective'
    content = Path(package).read_bytes()
    result = evaluate_reference(content, uuid4(), uuid4())
    assert result['compatibility'] == 'COMPATIBLE_REFERENCE_RUNTIME'
    assert result['versions'] == REFERENCE_VERSIONS and result['version_warnings'] == []
    assert result['model_sha256'] == MODEL_SHA256 and len(result['runtime_lock_sha256']) == 64
    assert result['refitted'] is False and result['prediction_mismatches'] == 0
    assert result['metrics']['n'] == 60 and result['metrics']['correct'] == 49
    assert result['metrics']['accuracy'] == pytest.approx(49 / 60)
    assert result['metrics']['f1_macro'] == pytest.approx(.7930479204842023)
    assert result['metrics']['alert_proposals'] == 40
    values = dict(zip(FEATURES, [10, .7, .5]))
    partial = partial_reference(content, 'B2', values, dict.fromkeys(FEATURES, '2026-06-30T00:00:00-05:00'))
    assert partial['risk_level'] == 'HIGH' and partial['compatibility'] == result['compatibility']
    with pytest.raises(RetrospectiveError, match='TEMPORAL_LEAKAGE'):
        partial_reference(content, 'B2', values, dict.fromkeys(FEATURES, '2026-07-01T00:00:00-05:00'))
