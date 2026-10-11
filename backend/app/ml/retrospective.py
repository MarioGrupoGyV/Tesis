"""EVAL_RETRO_V1: frozen user-supplied SVM, never fits or activates a model.

Only the explicitly reviewed package is accepted. Its scripts are never executed.
The derived CSV proves aggregate declared availability, not original source events.
"""
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import platform
import warnings
import zipfile
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import scipy
import sklearn
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

FEATURES = ('promedio_parcial_0_20', 'asistencia_parcial_proporcion', 'entrega_parcial_proporcion')
CUTS = {'B1': '2026-04-21', 'B2': '2026-06-30'}
CLASSES = ('LOW', 'MEDIUM', 'HIGH')
SOURCE_CLASSES = ('Bajo', 'Medio', 'Alto')
LIMA = ZoneInfo('America/Lima')
PACKAGE_SHA256 = '08ace0a90feb05e29d1ff5dedb6bd126139fd42ca85df06c5ef5802a70a86de4'
MODEL_SHA256 = '69efc39488faec44b25fd151d638659b4bcc7189d644e0cd96ccec2667137c15'
MAX_PACKAGE = 2 * 1024 * 1024


class RetrospectiveError(ValueError):
    """Sanitized codes only: never include input rows or personal identifiers."""


def sha(content):
    return hashlib.sha256(content).hexdigest()


def instant(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=LIMA) if parsed.tzinfo is None else parsed
    except (TypeError, ValueError):
        raise RetrospectiveError('RETROSPECTIVE_INVALID_DATE') from None


def cutoff(term):
    # The source script compares to midnight, not the end of the cutoff day.
    return instant(CUTS[term])


def vector(values):
    if set(values) != set(FEATURES):
        raise RetrospectiveError('RETROSPECTIVE_FEATURE_ORDER')
    try:
        result = np.array([float(values[name]) for name in FEATURES], dtype=float)
    except (TypeError, ValueError):
        raise RetrospectiveError('RETROSPECTIVE_INSUFFICIENT_DATA') from None
    if not np.isfinite(result).all() or not 0 <= result[0] <= 20 or not np.all((result[1:] >= 0) & (result[1:] <= 1)):
        raise RetrospectiveError('RETROSPECTIVE_OUT_OF_SCALE')
    return result


def inspect_package(content):
    if len(content) > MAX_PACKAGE or sha(content) != PACKAGE_SHA256:
        raise RetrospectiveError('RETROSPECTIVE_UNTRUSTED_PACKAGE')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or any('/' in n or '\\' in n for n in names):
                raise RetrospectiveError('RETROSPECTIVE_INVALID_ARCHIVE')
            files = {entry.filename: archive.read(entry) for entry in archive.infolist()
                     if entry.file_size <= MAX_PACKAGE}
            hashes = json.loads(files['hashes_archivos.json'])
            if any(sha(data) != hashes.get(name) for name, data in files.items() if name != 'hashes_archivos.json'):
                raise RetrospectiveError('RETROSPECTIVE_HASH_MISMATCH')
            protocol = json.loads(files['protocolo.json'])
            if protocol['id'] != 'EVAL_RETRO_V1' or protocol['cortes'] != CUTS or protocol['predictores'] != list(FEATURES):
                raise RetrospectiveError('RETROSPECTIVE_PROTOCOL_MISMATCH')
            selection = json.loads(files['seleccion_solo_B1.json'])
            if selection['modelo_seleccionado'] != 'SVM':
                raise RetrospectiveError('RETROSPECTIVE_SELECTION_MISMATCH')
            rows = list(csv.DictReader(io.StringIO(files['base_derivada_sin_nombres.csv'].decode('utf-8-sig'))))
            expected = list(csv.DictReader(io.StringIO(files['predicciones_B2.csv'].decode('utf-8-sig'))))
            results = json.loads(files['resultados.json'])
            validate_rows(rows)
            return files, rows, expected, results
    except (KeyError, TypeError, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError):
        raise RetrospectiveError('RETROSPECTIVE_INVALID_PACKAGE') from None


def validate_rows(rows):
    if len(rows) != 120:
        raise RetrospectiveError('RETROSPECTIVE_PARTITION_SIZE')
    seen = set()
    students = {term: set() for term in CUTS}
    for row in rows:
        try:
            term = row['bimestre']
            key = (term, row['codigo_estudiante'])
            if term not in CUTS or key in seen or row['registro_id'] != f"{key[1]}_{term}" or row['corte_logico'] != CUTS[term]:
                raise RetrospectiveError('RETROSPECTIVE_PARTITION_MISMATCH')
            seen.add(key)
            students[term].add(key[1])
            vector({name: row[name] for name in FEATURES})
            cut = cutoff(term)
            close = instant(row['cierre_bimestre'])
            reference = instant(row['fecha_referencia_disponible'])
            if (instant(row['ultima_disponibilidad_predictores']) > cut or close <= cut
                    or reference < close or (close.date() - cut.date()).days != int(row['horizonte_dias'])):
                raise RetrospectiveError('RETROSPECTIVE_TEMPORAL_LEAKAGE')
            if row['riesgo_referencia'] not in SOURCE_CLASSES:
                raise RetrospectiveError('RETROSPECTIVE_INVALID_REFERENCE')
            if term == 'B1' and reference >= cutoff('B2'):
                raise RetrospectiveError('RETROSPECTIVE_TRAIN_LABEL_AFTER_TEST_CUTOFF')
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, RetrospectiveError):
                raise
            raise RetrospectiveError('RETROSPECTIVE_INVALID_ROW') from None
    if any(len(group) != 60 for group in students.values()) or students['B1'] != students['B2']:
        raise RetrospectiveError('RETROSPECTIVE_COHORT_MISMATCH')


def load_frozen(files, rows):
    model_bytes = files['modelo_seleccionado.joblib']
    if sha(model_bytes) != MODEL_SHA256:
        raise RetrospectiveError('RETROSPECTIVE_UNTRUSTED_MODEL')
    # Byte identity is established against reviewed package/model constants BEFORE
    # deserialization; never accept joblib uploads, scripts, URLs or arbitrary paths.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model = joblib.load(io.BytesIO(model_bytes))
    if (type(model) is not Pipeline or list(model.named_steps) != ['standardscaler', 'svc']
            or type(model.named_steps['standardscaler']) is not StandardScaler
            or type(model.named_steps['svc']) is not SVC or model.n_features_in_ != 3
            or list(model.classes_) != [0, 1, 2] or model.named_steps['svc'].probability
            or model.named_steps['svc'].kernel != 'rbf'):
        raise RetrospectiveError('RETROSPECTIVE_MODEL_SCHEMA')
    train = np.stack([vector({k: r[k] for k in FEATURES}) for r in rows if r['bimestre'] == 'B1'])
    scaler = model.named_steps['standardscaler']
    if (int(scaler.n_samples_seen_) != 60 or not np.allclose(scaler.mean_, train.mean(axis=0), rtol=0, atol=1e-12)
            or not np.allclose(scaler.var_, train.var(axis=0), rtol=0, atol=1e-12)):
        raise RetrospectiveError('RETROSPECTIVE_SCALER_NOT_B1')
    svm = model.named_steps['svc']
    if (svm.C != 1.0 or svm.gamma != 'scale' or svm.class_weight != 'balanced'
            or np.any(svm.support_ < 0) or np.any(svm.support_ >= 60)
            or not np.allclose(svm.support_vectors_, scaler.transform(train)[svm.support_], rtol=0, atol=1e-12)):
        raise RetrospectiveError('RETROSPECTIVE_SUPPORT_VECTORS_NOT_B1')
    version_warnings = sorted({
        f'{w.message.estimator_name}: {w.message.original_sklearn_version} -> {w.message.current_sklearn_version}'
        if isinstance(w.message, InconsistentVersionWarning) else f'{w.category.__name__}: {w.message}'
        for w in caught})
    return model, version_warnings


def predict_partial(model, term, values, availability):
    if term not in CUTS or set(availability) != set(FEATURES):
        raise RetrospectiveError('RETROSPECTIVE_INVALID_CUTOFF')
    if any(instant(value) > cutoff(term) for value in availability.values()):
        raise RetrospectiveError('RETROSPECTIVE_TEMPORAL_LEAKAGE')
    predicted = int(model.predict(vector(values).reshape(1, 3))[0])
    if predicted not in (0, 1, 2):
        raise RetrospectiveError('RETROSPECTIVE_INVALID_CLASS')
    return {'risk_level': CLASSES[predicted], 'alert_proposed': predicted > 0,
            'probabilities_calibrated': False, 'notification_sent': False, 'intervention_performed': False}


def evaluate(content, run_id, actor_id):
    start = datetime.now(timezone.utc)
    files, rows, expected, source_results = inspect_package(content)
    model, version_warnings = load_frozen(files, rows)
    test = sorted((r for r in rows if r['bimestre'] == 'B2'), key=lambda r: r['codigo_estudiante'])
    predictions = []
    y, predicted = [], []
    expected_by_code = {r['codigo_estudiante']: r for r in expected}
    if len(expected) != 60 or set(expected_by_code) != {r['codigo_estudiante'] for r in test}:
        raise RetrospectiveError('RETROSPECTIVE_EXPECTED_PARTITION')
    for index, row in enumerate(test, 1):
        result = predict_partial(model, 'B2', {k: row[k] for k in FEATURES},
                                 {k: row['ultima_disponibilidad_predictores'] for k in FEATURES})
        truth = SOURCE_CLASSES.index(row['riesgo_referencia'])
        pred = CLASSES.index(result['risk_level'])
        y.append(truth)
        predicted.append(pred)
        original = expected_by_code[row['codigo_estudiante']]
        predictions.append({'row_number': index, **result, 'reference_risk': CLASSES[truth],
                            'correct': truth == pred, 'matches_package': SOURCE_CLASSES[pred] == original['riesgo_predicho']})
    cm = confusion_matrix(y, predicted, labels=[0, 1, 2])
    _, _, f1, support = precision_recall_fscore_support(y, predicted, labels=[0, 1, 2], zero_division=0)
    discrepancies = []
    mismatches = sum(not r['matches_package'] for r in predictions)
    actual = {'n': 60, 'correct': int(np.trace(cm)), 'accuracy': float(np.trace(cm) / 60),
              'f1_macro': float(np.mean(f1)), 'confusion': cm.tolist(), 'support': support.tolist(),
              'alert_proposals': sum(r['alert_proposed'] for r in predictions)}
    source_metrics = source_results['evaluacion_B2']['SVM']
    if mismatches:
        discrepancies.append(f'PREDICTION_MISMATCHES:{mismatches}')
    if not np.isclose(actual['accuracy'], source_metrics['accuracy'], rtol=0, atol=1e-12):
        discrepancies.append('ACCURACY_MISMATCH')
    if not np.isclose(actual['f1_macro'], source_metrics['f1_macro'], rtol=0, atol=1e-12):
        discrepancies.append('F1_MACRO_MISMATCH')
    if actual['alert_proposals'] != source_results['salidas_evaluador']['alertas_propuestas']:
        discrepancies.append('ALERT_PROPOSALS_MISMATCH')
    missing = sorted(set(json.loads(files['hashes_archivos.json'])) - set(files))
    return {'id': str(run_id), 'actor_id': str(actor_id), 'scope': 'RETROSPECTIVE_EVALUATION',
            'data_origin': 'REAL_USER_AUTHORIZED_UNVERIFIED', 'protocol_id': 'EVAL_RETRO_V1',
            'executed_at': start.isoformat(), 'completed_at': datetime.now(timezone.utc).isoformat(),
            'training_term': 'B1', 'evaluation_term': 'B2', 'cutoffs': CUTS, 'feature_order': list(FEATURES),
            'algorithm': 'SVM', 'model_sha256': MODEL_SHA256, 'package_sha256': PACKAGE_SHA256,
            'dataset_sha256': sha(files['base_derivada_sin_nombres.csv']), 'source_input_sha256': source_results['input_sha256'],
            'seed_declared_in_package': 20261011, 'refitted': False, 'scaler_b1_verified': True,
            'b1_support_vectors_verified': True,
            'temporal_check': 'DERIVED_AGGREGATE_ONLY', 'source_events_verified': False,
            'same_cohort': True, 'versions': {'python': platform.python_version(), 'scikit_learn': sklearn.__version__,
                'numpy': np.__version__, 'scipy': scipy.__version__, 'joblib': joblib.__version__},
            'source_versions': source_results['versiones'], 'version_warnings': version_warnings,
            'compatibility': 'CROSS_VERSION_EXPERIMENTAL' if version_warnings else 'SOURCE_SKLEARN_VERSION',
            'metrics': actual, 'prediction_mismatches': mismatches, 'discrepancies': discrepancies,
            'missing_package_files': missing, 'notifications_sent': 0, 'interventions_performed': 0,
            'predictions': predictions}
