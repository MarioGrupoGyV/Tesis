"""Reemplaza semillas: bootstrap explícito, rollback y bloqueo sin bypass por entorno."""
from uuid import uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.bootstrap_admin import AdministratorInput, BootstrapError, create_first_admin
from app.core.security import password_verify
from app.services.processing_policy import require_processing_protocol
from app.core.errors import AppError
from app.models.s1 import AuditEvent


def test_first_admin_atomic_and_repeat_rejected(db, synthetic_password):
    values = AdministratorInput(email='bootstrap-'+uuid4().hex+'@example.com', display_name='Fixture aislado', password=synthetic_password)
    with Session(bind=db, join_transaction_mode='create_savepoint') as session:
        assert session.scalar(text("SELECT count(*) FROM risk_school.app_users WHERE role='ADMIN'")) == 0
        user_id = create_first_admin(session, values)
        record = db.execute(text('SELECT password_hash FROM risk_school.app_users WHERE id=:id'), {'id':user_id}).scalar_one()
        assert record != synthetic_password and password_verify(synthetic_password, record)
        assert db.scalar(text("SELECT count(*) FROM risk_school.audit_events WHERE action='FIRST_ADMIN_CREATED'")) == 1
        with pytest.raises(BootstrapError):
            create_first_admin(session, values)
        assert db.scalar(text('SELECT count(*) FROM risk_school.academic_periods')) == 0


def test_bootstrap_audit_failure_rolls_back(db, synthetic_password, monkeypatch):
    values = AdministratorInput(email='rollback-'+uuid4().hex+'@example.com', display_name='Fixture rollback', password=synthetic_password)
    with Session(bind=db, join_transaction_mode='create_savepoint') as session:
        original = session.add
        def fail(record, *args, **kwargs):
            if isinstance(record, AuditEvent):
                # La cuenta ya se insertó mediante flush, pero aún no hay commit.
                assert session.scalar(text('SELECT count(*) FROM risk_school.app_users WHERE email=:email'), {'email':str(values.email)}) == 1
                raise RuntimeError('fixture failure')
            return original(record, *args, **kwargs)
        monkeypatch.setattr(session, 'add', fail)
        with pytest.raises(RuntimeError):
            create_first_admin(session, values)
    assert db.scalar(text('SELECT count(*) FROM risk_school.app_users WHERE email=:email'), {'email':str(values.email)}) == 0


@pytest.mark.parametrize('variable', ['REAL_MODE_ENABLED','DATA_ORIGIN','APP_ENV'])
def test_environment_cannot_enable_processing(monkeypatch, variable):
    monkeypatch.setenv(variable, 'true')
    with pytest.raises(AppError) as caught:
        require_processing_protocol()
    assert caught.value.code == 'INSTITUTIONAL_PROCESSING_NOT_READY'


def test_empty_context_login_and_blocked_import_without_file(db, client, synthetic_password):
    values = AdministratorInput(email='access-'+uuid4().hex+'@example.com', display_name='Fixture aislado', password=synthetic_password)
    with Session(bind=db, join_transaction_mode='create_savepoint') as session:
        create_first_admin(session, values)
    login = client.post('/api/v1/auth/login', json={'email':str(values.email),'password':synthetic_password}, headers={'Origin':'http://testserver'})
    assert login.status_code == 200
    headers = {'X-CSRF-Token':login.json()['csrf_token']}
    assert client.get('/api/v1/periods').json() == []
    assert client.post('/api/v1/imports/preview').status_code == 403
    response = client.post('/api/v1/imports/preview', headers=headers)
    assert response.status_code == 422
    assert response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    response = client.post('/api/v1/imports/'+str(uuid4())+'/commit', headers=headers, json={'expected_preview_version':1})
    assert response.status_code == 422 and response.json()['code'] == 'INSTITUTIONAL_PROCESSING_NOT_READY'
    for table in ('students','academic_snapshots','import_batches','model_versions','predictions'):
        assert db.scalar(text(f'SELECT count(*) FROM risk_school.{table}')) == 0
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 204
    assert client.get('/api/v1/auth/me').status_code == 401
