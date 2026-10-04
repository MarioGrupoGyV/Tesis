"""Núcleo S3 sobre PostgreSQL aislado. Modelos de fixture siempre INACTIVOS."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import threading
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, DBAPIError

from app.core.errors import AppError
from app.models.ml import ModelVersion, PredictionRecord
from app.models.s1 import AcademicPeriod, AuditEvent
from app.models.s2 import SnapshotRecord, StudentRecord
from app.ml.predict import PredictionResult
from app.repositories.ml import select_snapshots
from app.services import ml as service
from test_s2_imports import env, preview, assert_preview, commit, row, login_as
from test_s3_ml import ml_dataset, bundles

SAMPLES=[]


@pytest.fixture(scope='module',autouse=True)
def write_samples(tmp_path_factory):
    yield
    destination=Path('/evidence') if Path('/evidence').exists() else tmp_path_factory.mktemp('evidence')
    prefix = os.environ.get('TEST_REPORT_NAME', 's3-local-backend').removesuffix('-backend')
    (destination / (prefix + '-ml-response-samples.json')).write_text(
        json.dumps(SAMPLES,indent=2)+'\n', encoding='utf-8')


@pytest.fixture
def ml_db(env,bundles):
    batch=assert_preview(preview(env))
    assert commit(env,batch).status_code==200
    bundle=bundles['DUMMY']
    with env.app.state.database.session_factory() as db:
        assert db.scalar(text('SELECT current_user'))=='riesgo_app'
        snapshot=db.scalar(select(SnapshotRecord).where(SnapshotRecord.import_batch_id==batch['id']))
        student=db.scalar(select(StudentRecord).where(StudentRecord.anon_code==env.prefix))
        student.eligible_for_processing=True; student.consent_documented=True; student.assent_documented=True
        model=ModelVersion(name=env.prefix,version='fixture',algorithm='DUMMY',data_origin='REAL',
            dataset_hash=bundle.manifest['dataset_hash'],artifact_sha256='0'*64,artifact_key=uuid4().hex,
            feature_schema_version='ml-features-v1',reference_criterion_version=bundle.config.criterion_version,
            status='EVALUATED',is_active=False,parameters={},metrics={},manifest={'scope':'ISOLATED_TEST'})
        db.add(model); db.commit()
        return SimpleNamespace(env=env,snapshot=snapshot.id,model=model.id,period=snapshot.period_id,
            student=student.id,bundle=bundle)


def persist(db,state,**overrides):
    return service.persist_evaluated(db,**dict(snapshot_id=state.snapshot,model_id=state.model,
        result=PredictionResult('EVALUATED',risk_level='HIGH'),actor_id=state.env.context['accounts']['ADMIN']['id'],
        request_id=uuid4(),**overrides))


def test_idempotency_atomic_audit_and_immutability(ml_db):
    state=ml_db
    with state.env.app.state.database.session_factory() as db:
        record,created=persist(db,state); db.commit()
        identifier=record.id
        assert created and not record.probabilities_calibrated and record.probability_low is None
    with state.env.app.state.database.session_factory() as db:
        record,created=persist(db,state); db.commit()
        assert not created and record.id==identifier
        assert db.scalar(select(text('count(*)')).select_from(AuditEvent).where(AuditEvent.entity_id==identifier))==1
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE risk_school.predictions SET risk_level='LOW' WHERE id=:id"),{'id':identifier})
        db.rollback()


def test_intermediate_failure_rolls_back_prediction_and_audit(ml_db):
    state=ml_db
    with state.env.app.state.database.session_factory() as db:
        with pytest.raises(IntegrityError):
            service.persist_evaluated(db,snapshot_id=state.snapshot,model_id=state.model,
                result=PredictionResult('EVALUATED',risk_level='HIGH'),actor_id=uuid4(),request_id=uuid4())
        db.rollback()
        assert db.scalar(select(PredictionRecord).where(PredictionRecord.snapshot_id==state.snapshot)) is None


def test_concurrent_prediction_reuses_unique_result(ml_db):
    barrier=threading.Barrier(2)
    def work():
        with ml_db.env.app.state.database.session_factory() as db:
            assert db.scalar(text('SELECT current_user'))=='riesgo_app'
            barrier.wait(timeout=10)
            result,created=persist(db,ml_db)
            db.commit()
            return result.id,created
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(work) for _ in range(2)]
        values=[f.result(timeout=20) for f in futures]
    assert values[0][0]==values[1][0] and sum(v[1] for v in values)==1
    with ml_db.env.app.state.database.session_factory() as db:
        assert db.scalar(select(text('count(*)')).select_from(AuditEvent).where(AuditEvent.entity_id==values[0][0]))==1


def test_abstention_does_not_insert(ml_db):
    with ml_db.env.app.state.database.session_factory() as db:
        result=service.persist_evaluated(db,snapshot_id=ml_db.snapshot,model_id=ml_db.model,
            result=PredictionResult('INSUFFICIENT_DATA','missing'),actor_id=None,request_id=uuid4())
        assert result==(None,False)
        db.commit()
        assert db.scalar(select(PredictionRecord).where(PredictionRecord.snapshot_id==ml_db.snapshot)) is None


def test_locked_period_and_ineligible_student(ml_db):
    with ml_db.env.app.state.database.session_factory() as db:
        period=db.get(AcademicPeriod,ml_db.period); period.is_locked=True; db.commit()
        with pytest.raises(AppError) as error: persist(db,ml_db)
        assert error.value.code=='PERIOD_LOCKED'
        db.rollback(); period=db.get(AcademicPeriod,ml_db.period); period.is_locked=False
        student=db.get(StudentRecord,ml_db.student); student.eligible_for_processing=False; db.commit()
        with pytest.raises(AppError) as error: persist(db,ml_db)
        assert error.value.code=='NOT_ELIGIBLE'


def test_as_of_revision_and_core_inference(ml_db):
    state=ml_db; env=state.env
    before=datetime.now(UTC)
    with env.app.state.database.session_factory() as db:
        chosen=select_snapshots(db,state.period,before)
        assert len(chosen)==1 and chosen[0]['id']==state.snapshot
        period=db.get(AcademicPeriod,state.period); model=db.get(ModelVersion,state.model)
        actor=SimpleNamespace(id=env.context['accounts']['ADMIN']['id'])
        result=service.infer_selected(db,actor,period,before,model,state.bundle,uuid4())
        db.commit()
        assert result.created==1 and not result.abstentions
        SAMPLES.append({'schema':'PredictionRunResult','body':result.model_dump(mode='json')})
    correction=assert_preview(preview(env,[row(env,average_grade='15')]))
    assert commit(env,correction).status_code==200
    with env.app.state.database.session_factory() as db:
        assert select_snapshots(db,state.period,before)[0]['id']==state.snapshot
        newer=select_snapshots(db,state.period,datetime.now(UTC))[0]
        assert newer['revision']==2 and newer['id']!=state.snapshot
        assert db.scalar(select(PredictionRecord).where(PredictionRecord.snapshot_id==newer['id'])) is None
        assert select_snapshots(db,state.period,datetime(2026,5,1,tzinfo=UTC))==[]
    detail=env.client.get(f'/api/v1/students/{state.student}',params={'period_id':str(state.period)}).json()
    assert detail['latest_prediction'] is None and detail['student']['evaluation_status']=='NOT_EVALUATED'


def test_read_scopes_and_public_model_projection(ml_db):
    state=ml_db; env=state.env
    with env.app.state.database.session_factory() as db:
        record,_=persist(db,state); db.commit(); identifier=record.id
    for role in ('ADMIN','TUTOR','DIRECTOR','RESEARCHER'):
        login_as(env,role)
        response=env.client.get(f'/api/v1/predictions/{identifier}')
        assert response.status_code==(403 if role=='RESEARCHER' else 200)
        if response.status_code==200:
            SAMPLES.append({'schema':'Prediction','body':response.json()})
            assert set(response.json())=={'id','enrollment_id','snapshot_id','model_id','data_origin',
                'risk_level','cutoff_at','target_date','predicted_at','probability_low','probability_medium',
                'probability_high','probabilities_calibrated'}
    with env.app.state.database.session_factory() as db:
        from app.models.s1 import GradeSection
        section=db.get(GradeSection,env.context['sections'][0]['id']); section.tutor_id=None; db.commit()
    login_as(env,'TUTOR')
    assert env.client.get(f'/api/v1/predictions/{identifier}').status_code==404
    login_as(env,'ADMIN')
    response=env.client.get(f'/api/v1/models/{state.model}')
    assert response.status_code==200 and not response.json()['is_active']
    SAMPLES.append({'schema':'Model','body':response.json()})
    assert not {'artifact_key','manifest','dataset_hash','metrics','parameters'} & set(response.json())


def test_model_activation_constraints_preserved(ml_db):
    with ml_db.env.app.state.database.session_factory() as db:
        constraints=db.execute(text("SELECT conname FROM pg_constraint WHERE conrelid='risk_school.model_versions'::regclass")).scalars().all()
        # S3.1 explicitly replaces the old total activation prohibition. The
        # fixture is still REAL and may never become active in this iteration.
        assert 'synthetic_only_active_model' in constraints
        assert not {'model_activation_pending','demo_only_active_model'} & set(constraints)
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE risk_school.model_versions SET status='APPROVED',is_active=true WHERE id=:id"),{'id':ml_db.model})
        db.rollback()


def test_core_rejects_model_bundle_mismatch(ml_db):
    with ml_db.env.app.state.database.session_factory() as db:
        model=db.get(ModelVersion,ml_db.model)
        model.dataset_hash='f'*64
        with pytest.raises(AppError) as error:
            service.infer_selected(db,SimpleNamespace(id=None),db.get(AcademicPeriod,ml_db.period),
                datetime.now(UTC),model,ml_db.bundle,uuid4())
        assert error.value.code=='MODEL_INCOMPATIBLE'
        db.rollback()
