"""Only this isolated, pinned interpreter serves retrospective inference. No fallback."""
import base64
import json
import os
from pathlib import Path
import subprocess

from app.ml.retrospective import MAX_PACKAGE, MODEL_SHA256, PACKAGE_SHA256, RetrospectiveError, sha

REFERENCE_VERSIONS = {'python': '3.12.14', 'scikit_learn': '1.8.0', 'numpy': '2.3.5',
                      'scipy': '1.17.0', 'joblib': '1.5.3', 'threadpoolctl': '3.6.0'}


def invoke(action, content=None, **arguments):
    executable = Path(os.environ.get('RETROSPECTIVE_PYTHON', '/opt/retrospective/bin/python3.12'))
    if not executable.is_absolute() or not executable.is_file():
        raise RetrospectiveError('RETROSPECTIVE_REFERENCE_RUNTIME_UNAVAILABLE')
    if content is not None and (len(content) > MAX_PACKAGE or sha(content) != PACKAGE_SHA256):
        raise RetrospectiveError('RETROSPECTIVE_UNTRUSTED_PACKAGE')
    payload = {'action': action, **arguments}
    if content is not None:
        payload['package_base64'] = base64.b64encode(content).decode('ascii')
    # Do not pass database credentials, secrets, PYTHONPATH or parent site-packages.
    environment = {'LANG': 'C.UTF-8', 'PATH': '/usr/bin:/bin',
                   'LD_LIBRARY_PATH': str(executable.parent.parent / 'lib'),
                   'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    worker = Path(__file__).with_name('retrospective_worker.py')
    try:
        result = subprocess.run([str(executable), '-I', str(worker)],
            input=json.dumps(payload, allow_nan=False), text=True, capture_output=True,
            env=environment, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RetrospectiveError('RETROSPECTIVE_REFERENCE_RUNTIME_UNAVAILABLE') from None
    try:
        envelope = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise RetrospectiveError('RETROSPECTIVE_REFERENCE_RUNTIME_FAILED') from None
    if result.returncode or 'error' in envelope:
        code = envelope.get('error', '')
        if not isinstance(code, str) or not code.startswith('RETROSPECTIVE_') or not code.replace('_', '').isalnum():
            code = 'RETROSPECTIVE_REFERENCE_RUNTIME_FAILED'
        raise RetrospectiveError(code)
    if result.stderr.strip():
        # Never silently drop diagnostics which escaped the worker's warning journal.
        raise RetrospectiveError('RETROSPECTIVE_REFERENCE_UNRECORDED_WARNING')
    if envelope.get('versions') != REFERENCE_VERSIONS or envelope.get('model_sha256') != MODEL_SHA256:
        raise RetrospectiveError('RETROSPECTIVE_REFERENCE_VERSION_MISMATCH')
    return envelope['result']


def evaluate_reference(content, run_id, actor_id):
    return invoke('evaluate', content, run_id=str(run_id), actor_id=str(actor_id))


def partial_reference(content, term, values, availability):
    return invoke('partial', content, term=term, values=values, availability=availability)
