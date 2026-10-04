"""Rutas reales con riesgo_app; sin sustituir el bloqueo de ML."""
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.core.database import get_db


@pytest.mark.parametrize('path',['/models','/models/'+str(uuid4()),'/predictions/'+str(uuid4())])
def test_ml_anonymous(client,path):
    assert client.get('/api/v1'+path).status_code==401


@pytest.mark.parametrize('role',['ADMIN','TUTOR','DIRECTOR','RESEARCHER'])
def test_ml_roles_and_blocking(client,login,role,db):
    result=login(role).json()
    headers={'X-CSRF-Token':result['csrf_token']}
    models=client.get('/api/v1/models')
    assert models.status_code==(200 if role=='ADMIN' else 403)
    if role=='ADMIN':
        for model in models.json()['items']:
            assert not {'manifest','dataset_hash','artifact_key','parameters','metrics'} & set(model)
    assert client.get('/api/v1/models/'+str(uuid4())).status_code==(404 if role=='ADMIN' else 403)
    assert client.get('/api/v1/predictions/'+str(uuid4())).status_code==(403 if role=='RESEARCHER' else 404)
    before=db.scalar(text('SELECT count(*) FROM risk_school.predictions'))
    assert client.post('/api/v1/predictions/run').status_code==403
    assert client.post('/api/v1/predictions/run',headers={'X-CSRF-Token':'wrong'}).status_code==403
    response=client.post('/api/v1/predictions/run',headers=headers,content=b'not json')
    assert response.status_code==(422 if role=='ADMIN' else 403)
    assert response.json()['code']==('INSTITUTIONAL_PROCESSING_NOT_READY' if role=='ADMIN' else 'FORBIDDEN')
    assert db.scalar(text('SELECT count(*) FROM risk_school.predictions'))==before


def test_ml_anonymous_write_before_protocol(client):
    assert client.post('/api/v1/predictions/run',content=b'not json').status_code==401


def test_ml_db_failure_sanitized(client,app):
    def failure():
        raise OperationalError('secret SQL','private parameters',Exception('private error'))
        yield
    app.dependency_overrides[get_db]=failure
    response=client.get('/api/v1/models')
    assert response.status_code==503 and response.json()['code']=='SERVICE_UNAVAILABLE'
    assert 'private' not in response.text and 'SQL' not in response.text


def test_no_activation_or_training_http(client):
    assert client.post('/api/v1/models/'+str(uuid4())+'/activate').status_code==404
    assert client.post('/api/v1/models/train').status_code==405
