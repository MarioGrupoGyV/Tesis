"""JSON stdin/stdout worker, isolated from API interpreter, never writes data."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import warnings

# -I deliberately excludes the application's import path; only this fixed code root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import joblib
import numpy
import scipy
import sklearn
import threadpoolctl

from app.ml.retrospective import (MAX_PACKAGE, MODEL_SHA256, RetrospectiveError,
    evaluate, inspect_package, load_frozen, predict_partial)
from app.ml.retrospective_runtime import REFERENCE_VERSIONS


def versions():
    return {'python': platform.python_version(), 'scikit_learn': sklearn.__version__,
            'numpy': numpy.__version__, 'scipy': scipy.__version__,
            'joblib': joblib.__version__, 'threadpoolctl': threadpoolctl.__version__}


def check_runtime():
    actual = versions()
    if actual != REFERENCE_VERSIONS or not sys.flags.isolated:
        raise RetrospectiveError('RETROSPECTIVE_REFERENCE_VERSION_MISMATCH')
    return actual


def forbid_fit(*args, **kwargs):
    raise RetrospectiveError('RETROSPECTIVE_FIT_FORBIDDEN')


def execute_checked(payload):
    actual = check_runtime()  # Before deserialization, with no warning suppression.
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    for estimator in (Pipeline, StandardScaler, SVC):
        estimator.fit = forbid_fit
    if payload['action'] == 'probe':
        result = {'versions': actual, 'isolated': True, 'prefix': sys.prefix}
    else:
        content = base64.b64decode(payload['package_base64'], validate=True)
        if payload['action'] == 'evaluate':
            result = evaluate(content, payload['run_id'], payload['actor_id'])
        else:
            files, rows, _, _ = inspect_package(content)
            model, caught = load_frozen(files, rows)
            result = {'version_warnings': caught}
            if payload['action'] == 'partial':
                result.update(predict_partial(model, payload['term'], payload['values'], payload['availability']),
                    executed_at=datetime.now(timezone.utc).isoformat(), scope='RETROSPECTIVE_EVALUATION')
            elif payload['action'] != 'inspect':
                raise RetrospectiveError('RETROSPECTIVE_INVALID_ACTION')
        result['versions'] = actual
        result['compatibility'] = 'COMPATIBLE_REFERENCE_RUNTIME'
        result['runtime_id'] = 'svm-reference-v1'
        lock = Path(sys.prefix) / 'requirements-retrospective.txt'
        result['runtime_lock_sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
    return {'versions': actual, 'model_sha256': MODEL_SHA256, 'result': result}


def execute(payload):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        envelope = execute_checked(payload)
    result = envelope['result']
    if payload['action'] != 'probe':
        result['version_warnings'] = sorted(set(result.get('version_warnings', [])) |
            {f'{warning.category.__name__}: {warning.message}' for warning in caught})
    return envelope


if __name__ == '__main__':
    try:
        payload = json.loads(sys.stdin.read(MAX_PACKAGE * 2))
        print(json.dumps(execute(payload), allow_nan=False))
    except Exception as error:
        code = str(error) if isinstance(error, RetrospectiveError) else 'RETROSPECTIVE_REFERENCE_RUNTIME_FAILED'
        print(json.dumps({'error': code}))
        sys.exit(1)
