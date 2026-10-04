"""Private study evidence must not reach CLI output or the general API status.

The generator and comparison run with isolated fixtures. No credentials, school
records or model artifacts from the active application are read by these tests.
"""
import json

import pytest
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.ml.synthetic import generate, load_config
from app.ml.train import ALGORITHMS, compare_study
from app.services.synthetic_study import comparison_safe, public_generation


@pytest.fixture(scope='module')
def projection_study():
    return generate(load_config(), 1729)


def keys_recursively(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys_recursively(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_recursively(item)


def assert_no_observation_identifiers(value, study):
    serialized = json.dumps(value, sort_keys=True, allow_nan=False)
    for observation in study.dataset.observations:
        assert observation.student_key not in serialized
        assert str(observation.snapshot_id) not in serialized
        assert str(observation.enrollment_id) not in serialized


def test_generation_output_keeps_provenance_without_private_groups_or_outcomes(projection_study):
    study = projection_study
    manifest = study.manifest_json
    # Future additions to the private manifest cannot implicitly become CLI data.
    private = {**manifest, 'future_private_extension': study.labels_json,
               'private_rows': study.dataset.model_dump(mode='json')}
    public = public_generation(private)
    assert public['scope'] == 'SYNTHETIC_STUDY'
    assert public['data_origin'] == 'SYNTHETIC'
    assert public['csv_sha256'] == manifest['csv_sha256']
    assert public['student_count'] == 60 and public['observation_count'] == 360
    assert public['generator_version'] == load_config().generator_version
    assert public['context']['school_year'] == 2025 and public['limits']
    assert not {'future_private_extension', 'private_rows', 'protocol',
                'development_students', 'external_students', 'outcomes',
                'future_outcome', 'student_code', 'student_key', 'risk'} & set(keys_recursively(public))
    assert_no_observation_identifiers(public, study)
    # Sanitization must preserve private traceability rather than deleting it.
    assert manifest['protocol']['development_students']
    assert manifest['protocol']['external_students']
    assert study.labels_json['outcomes'][0]['future_outcome']


def test_comparison_output_contains_aggregate_metrics_and_keeps_private_evidence(projection_study):
    comparison = compare_study(projection_study.dataset, load_config())
    public = comparison_safe(comparison.report)
    assert public['scope'] == 'SYNTHETIC_STUDY'
    assert public['student_count'] == 60
    assert public['development_student_count'] + public['external_student_count'] == 60
    assert set(public['algorithms']) == set(ALGORITHMS)
    assert public['folds_effective'] >= 2 and public['exclusions']
    private_keys = {'partitions', 'validation_predictions', 'external_predictions',
                    'student_code', 'student_key', 'snapshot_id', 'enrollment_id',
                    'development_students', 'external_students', 'train_students',
                    'validation_students', 'development_source_indices',
                    'external_source_indices', 'future_outcome', 'labels', 'outcomes'}
    assert not private_keys & set(keys_recursively(public))
    assert_no_observation_identifiers(public, projection_study)
    for algorithm, bundle in comparison.bundles.items():
        assert public['algorithms'][algorithm]['development'] == bundle.manifest['metrics']
        assert public['algorithms'][algorithm]['external'] == bundle.manifest['external_metrics']
        assert bundle.manifest['partitions']
        assert bundle.manifest['validation_predictions'][0]['snapshot_id']
        assert bundle.manifest['external_predictions'][0]['expected']


def test_processing_status_requires_session_and_researcher_receives_general_state_only(client, login):
    unauthenticated = client.get('/api/v1/processing/status')
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()['code'] == 'SESSION_INVALID'
    login('RESEARCHER')
    response = client.get('/api/v1/processing/status', headers={'X-Role': 'ADMIN'})
    assert response.status_code == 200
    status = response.json()
    assert set(status) == {'scope', 'notice', 'institutional_ready', 'synthetic_ready', 'operations'}
    assert status['scope'] == 'SYNTHETIC_STUDY' and status['institutional_ready'] is False
    assert status['notice'] == 'Estudio con datos sintéticos. No corresponde a estudiantes reales.'
    assert isinstance(status['synthetic_ready'], bool)
    assert set(status['operations']) == {'import', 'compare', 'register', 'activate',
                                        'predict', 'read_students', 'read_models',
                                        'read_alerts', 'write_followup', 'sync_alerts',
                                        'read_reports', 'export_reports'}
    for operation in status['operations'].values():
        assert set(operation) == {'available', 'reason'}
        assert operation['available'] is False
        assert operation['reason'] == 'ROLE_RESTRICTED'
    assert client.get('/api/v1/models', headers={'X-Role': 'ADMIN'}).status_code == 403
    assert client.get('/api/v1/periods', headers={'X-Role': 'ADMIN'}).status_code == 403


def test_processing_status_database_failure_is_sanitized(client, app, login):
    login('ADMIN')
    def unavailable():
        raise OperationalError('SELECT private_study_labels',
                               {'password': 'private-database-value'},
                               Exception('private connection details'))
        yield
    app.dependency_overrides[get_db] = unavailable
    response = client.get('/api/v1/processing/status')
    assert response.status_code == 503
    assert response.json()['code'] == 'SERVICE_UNAVAILABLE'
    assert all(value not in response.text for value in
               ('private_study_labels', 'private-database-value', 'private connection details', 'SELECT'))
