"""Retrospective tests use the authorized external ZIP; never retain its rows."""
from copy import deepcopy
from datetime import datetime, timezone
import csv
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import numpy as np
import pytest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sqlalchemy import text

from app.ml.retrospective import (CLASSES, CUTS, FEATURES, PACKAGE_SHA256, RetrospectiveError,
    evaluate, inspect_package, load_frozen, predict_partial, validate_rows, vector)
from app.repositories.retrospective import RetrospectiveStore
from app.services import retrospective as service


@pytest.fixture(scope='module')
def package():
    path = os.environ.get('RETROSPECTIVE_TEST_ZIP')
    if not path:
        pytest.skip('Supply authorized ZIP outside checkout through RETROSPECTIVE_TEST_ZIP')
    return Path(path).read_bytes()


@pytest.fixture(scope='module')
def inspected(package):
    return inspect_package(package)


def registration(actor=None):
    return {'authorized_local_processing': True, 'institutional_activation': False,
            'package_sha256': PACKAGE_SHA256, 'actor_id': str(actor or uuid4()), 'source_audit': None}


def test_untrusted_package_rejected_before_joblib(monkeypatch):
    monkeypatch.setattr('joblib.load', lambda *a, **k: pytest.fail('Must reject before deserialization'))
    with pytest.raises(RetrospectiveError, match='UNTRUSTED_PACKAGE'):
        inspect_package(b'untrusted')


@pytest.mark.parametrize('values', [
    [21, .9, .9], [-1, .9, .9], [15, 90, .9], [15, .9, 90],
    [None, .9, .9], [float('nan'), .9, .9], [15, float('inf'), .9],
])
def test_rejects_missing_and_invalid_scales(values):
    with pytest.raises(RetrospectiveError):
        vector(dict(zip(FEATURES, values)))


def test_exact_feature_order_and_no_extra_predictor():
    assert vector(dict(reversed(list(zip(FEATURES, [14, .8, .75]))))).tolist() == [14, .8, .75]
    with pytest.raises(RetrospectiveError, match='FEATURE_ORDER'):
        vector({**dict(zip(FEATURES, [14, .8, .75])), 'reference_risk': 2})


def test_frozen_model_reproduces_60_without_fit(package, monkeypatch):
    def forbidden(*a, **k):
        pytest.fail('No fitting during retrospective inference')
    for cls in (Pipeline, StandardScaler, SVC):
        monkeypatch.setattr(cls, 'fit', forbidden)
    result = evaluate(package, uuid4(), uuid4())
    assert result['metrics'] == {'n': 60, 'correct': 49, 'accuracy': 49 / 60,
        'f1_macro': pytest.approx(.7930479204842023), 'confusion': [[20,5,0],[0,9,2],[0,4,20]],
        'support': [25,11,24], 'alert_proposals': 40}
    assert result['prediction_mismatches'] == 0 and result['discrepancies'] == []
    assert result['refitted'] is False and result['scaler_b1_verified'] is True
    assert result['notifications_sent'] == result['interventions_performed'] == 0
    assert datetime.fromisoformat(result['executed_at']).date() >= datetime(2026,10,11).date()
    assert not any('codigo_estudiante' in row for row in result['predictions'])


@pytest.mark.parametrize('field,value,code', [
    ('ultima_disponibilidad_predictores', '2026-07-01', 'TEMPORAL_LEAKAGE'),
    ('corte_logico', '2026-07-01', 'PARTITION_MISMATCH'),
    ('fecha_referencia_disponible', '2026-06-01', 'TEMPORAL_LEAKAGE'),
    ('horizonte_dias', '99', 'TEMPORAL_LEAKAGE'),
])
def test_temporal_row_guard(inspected, field, value, code):
    rows = deepcopy(inspected[1])
    index = next(i for i, r in enumerate(rows) if r['bimestre'] == 'B2')
    rows[index][field] = value
    with pytest.raises(RetrospectiveError, match=code):
        validate_rows(rows)


def test_duplicate_cohort_and_b1_label_after_b2(inspected):
    rows = deepcopy(inspected[1])
    rows[-1] = deepcopy(rows[-2])
    with pytest.raises(RetrospectiveError, match='PARTITION_MISMATCH'):
        validate_rows(rows)
    rows = deepcopy(inspected[1])
    rows[0]['fecha_referencia_disponible'] = '2026-06-30'
    with pytest.raises(RetrospectiveError, match='TRAIN_LABEL_AFTER_TEST_CUTOFF'):
        validate_rows(rows)


def test_scaler_verified_against_b1_and_single_scaling(inspected):
    files, rows, _, _ = inspected
    model, _ = load_frozen(files, rows)
    for row in [r for r in rows if r['bimestre'] == 'B2']:
        values = {k: row[k] for k in FEATURES}
        x = vector(values).reshape(1,3)
        direct = model.named_steps['svc'].predict(model.named_steps['standardscaler'].transform(x))[0]
        predicted = predict_partial(model, 'B2', values, {k: row['ultima_disponibilidad_predictores'] for k in FEATURES})
        assert predicted['risk_level'] == CLASSES[direct]
    changed = deepcopy(rows)
    changed[0][FEATURES[0]] = str(float(changed[0][FEATURES[0]]) + .1)
    with pytest.raises(RetrospectiveError, match='SCALER_NOT_B1'):
        load_frozen(files, changed)


def test_partial_available_boundary_and_b1_cut(inspected):
    model, _ = load_frozen(inspected[0], inspected[1])
    values = dict(zip(FEATURES, [14, .8, .75]))
    available = dict.fromkeys(FEATURES, '2026-06-30T05:00:00+00:00')
    assert predict_partial(model, 'B2', values, available)['risk_level'] in CLASSES
    available[FEATURES[1]] = '2026-06-30T05:00:00.000001+00:00'
    with pytest.raises(RetrospectiveError, match='TEMPORAL_LEAKAGE'):
        predict_partial(model, 'B2', values, available)
    with pytest.raises(RetrospectiveError, match='TEMPORAL_LEAKAGE'):
        predict_partial(model, 'B1', values, dict.fromkeys(FEATURES, '2026-04-22T00:00:00-05:00'))


def test_private_journal_integrity_history_and_restart(package, tmp_path):
    store = RetrospectiveStore(tmp_path / 'ml')
    assert store.register(package, registration())
    assert not store.register(package, registration())
    user = SimpleNamespace(id=uuid4(), role='ADMIN')
    settings = SimpleNamespace(ml_storage_dir=tmp_path / 'ml')
    first = service.run(user, settings, uuid4())
    original = (store.root / store.run_name(first.id)).read_bytes()
    second = service.run(user, settings, uuid4())
    assert first.id != second.id
    assert (store.root / store.run_name(first.id)).read_bytes() == original
    restarted = RetrospectiveStore(tmp_path / 'ml')
    assert len(restarted.history()) == 2
    with pytest.raises(FileExistsError):
        restarted.save_run(restarted.run(first.id))
    envelope = json.loads(original)
    envelope['record']['metrics']['correct'] = 60
    (store.root / store.run_name(first.id)).write_text(json.dumps(envelope))
    with pytest.raises(RetrospectiveError, match='STORAGE_INTEGRITY'):
        restarted.run(first.id)


def test_no_private_storage_in_checkout():
    with pytest.raises(RetrospectiveError, match='PRIVATE_STORAGE_REQUIRED'):
        RetrospectiveStore(Path(__file__).resolve().parents[2] / '.local' / 'retrospective')


def test_api_roles_csrf_data_flow_and_academic_preservation(client, login, app, db, package, tmp_path):
    app.state.settings.ml_storage_dir = tmp_path / 'ml'
    tables = ['academic_snapshots', 'predictions', 'alerts', 'interventions', 'model_versions']
    before = {t: db.scalar(text('SELECT count(*) FROM risk_school.' + t)) for t in tables}
    root = '/api/v1/retrospective'
    assert client.get(root + '/evaluations').status_code == 401
    login()
    assert client.get(root + '/evaluations').json()['available'] is False
    token = client.get('/api/v1/auth/csrf').json()['csrf_token']
    assert client.post(root + '/evaluations').status_code == 403
    store = RetrospectiveStore(tmp_path / 'ml')
    store.register(package, registration())
    response = client.post(root + '/evaluations', headers={'X-CSRF-Token': token})
    assert response.status_code == 200
    record = response.json()
    assert record['metrics']['correct'] == 49 and len(record['predictions']) == 60
    identifier = record['id']
    csv_response = client.get(root + f'/evaluations/{identifier}/report.csv')
    assert csv_response.status_code == 200 and csv_response.text.startswith('\ufeff')
    export = list(csv.DictReader(io.StringIO(csv_response.text.lstrip('\ufeff'))))
    assert len(export) == 60
    assert sum(r['alert_proposed'] == 'True' for r in export) == 40
    assert all(r['notification_sent'] == r['intervention_performed'] == 'False' for r in export)
    assert 'codigo_estudiante' not in csv_response.text and 'nombre' not in csv_response.text
    assert client.get(root + '/evaluations?page=2&page_size=1').json()['items'] == []
    assert client.get(root + '/evaluations?page_size=101').status_code == 422
    assert client.get(root + f'/evaluations/{uuid4()}').status_code == 404
    payload = {'term': 'B2', 'values': dict(zip(FEATURES, [14, .8, .75])),
               'available_at': dict.fromkeys(FEATURES, '2026-06-30T00:00:00-05:00')}
    assert client.post(root + '/partial-prediction', json=payload, headers={'X-CSRF-Token': token}).status_code == 200
    payload['available_at'][FEATURES[2]] = '2026-07-01T00:00:00-05:00'
    assert client.post(root + '/partial-prediction', json=payload, headers={'X-CSRF-Token': token}).status_code == 422
    for role in ('TUTOR', 'DIRECTOR', 'RESEARCHER'):
        login(role)
        for path in ['/evaluations', f'/evaluations/{identifier}', f'/evaluations/{identifier}/report.csv']:
            assert client.get(root + path).status_code == 403
        assert client.post(root + '/evaluations', headers={'X-CSRF-Token': token}).status_code == 403
        assert client.post(root + '/partial-prediction', content=b'invalid').status_code == 403
    after = {t: db.scalar(text('SELECT count(*) FROM risk_school.' + t)) for t in tables}
    assert before == after
