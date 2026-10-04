from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import select
from app.core.errors import AppError
from app.models.ml import ModelVersion, PredictionRecord
from app.models.s1 import AcademicPeriod, AuditEvent
from app.models.s2 import SnapshotRecord, StudentRecord, EnrollmentRecord
from app.repositories import ml as repository
from app.repositories.students import selected_prediction
from app.schemas import ml as schemas
from app.schemas.s2 import Prediction
from app.services.processing_policy import require_ml_protocol
from app.services.students import projection


def require_admin(user):
    if user.role != 'ADMIN':
        raise AppError(403,'FORBIDDEN','Solo el administrador puede consultar modelos o solicitar inferencia.')


def list_models(db,user,page,page_size):
    require_admin(user)
    rows,total = repository.models(db,page,page_size)
    return schemas.ModelPage(items=[schemas.Model.model_validate(r) for r in rows],total=total,page=page,page_size=page_size)


def model_detail(db,user,id):
    require_admin(user)
    row = db.get(ModelVersion,id)
    if row is None or row.data_origin not in ('REAL','SYNTHETIC'):
        raise AppError(404,'MODEL_NOT_FOUND','El modelo no está disponible.')
    return schemas.Model.model_validate(row)


def prediction_detail(db,user,id):
    if user.role not in ('ADMIN','TUTOR','DIRECTOR'):
        raise AppError(403,'FORBIDDEN','No tienes acceso a predicciones.')
    row = repository.accessible_prediction(db,user,id)
    if row is None:
        # Igual para UUID inexistente o sección ajena: no permite enumerar casos.
        raise AppError(404,'PREDICTION_NOT_FOUND','La predicción no está disponible.')
    return projection(Prediction,selected_prediction(db,row.id))


def persist_evaluated(db, *, snapshot_id, model_id, result, actor_id, request_id):
    """Núcleo transaccional interno; el llamador confirma también auditoría. No activa modelos."""
    if result.status != 'EVALUATED' or result.risk_level not in ('LOW','MEDIUM','HIGH'):
        return None,False
    if result.probabilities_calibrated or any(getattr(result,k) is not None for k in
            ('probability_low','probability_medium','probability_high')):
        raise AppError(422,'CALIBRATION_NOT_IMPLEMENTED','S3 no persiste probabilidades calibradas.')
    snapshot = db.get(SnapshotRecord,snapshot_id)
    model = db.get(ModelVersion,model_id)
    if snapshot is None or model is None:
        raise AppError(404,'PREDICTION_RESOURCE_NOT_FOUND','No están disponibles el corte y modelo.')
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==snapshot.period_id).with_for_update(read=True))
    if period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado.')
    enrollment = db.get(EnrollmentRecord,snapshot.enrollment_id)
    student = db.get(StudentRecord,enrollment.student_id)
    if not (student.is_active and student.eligible_for_processing and
            (student.data_origin=='SYNTHETIC' or(student.consent_documented and student.assent_documented))):
        raise AppError(422,'NOT_ELIGIBLE','El corte no es elegible para inferencia.')
    if snapshot.data_origin != model.data_origin or snapshot.data_origin not in ('REAL','SYNTHETIC'):
        raise AppError(422,'ORIGIN_NOT_SUPPORTED','Corte y modelo deben conservar el mismo origen.')
    # La persistencia aislada prueba integridad con modelos inactivos. La selección
    # operativa exige protocolo + modelo aprobado/activo en run_period, sin bypass.
    if model.feature_schema_version != 'ml-features-v1' or snapshot.schema_version != 'academic-v1':
        raise AppError(409,'MODEL_INCOMPATIBLE','El esquema del modelo no es compatible.')
    row,created = repository.insert_prediction(db,dict(id=uuid4(),enrollment_id=snapshot.enrollment_id,
        snapshot_id=snapshot.id,model_id=model.id,data_origin=snapshot.data_origin,risk_level=result.risk_level,
        probabilities_calibrated=False,probability_low=None,probability_medium=None,probability_high=None))
    if row is None:
        raise AppError(409,'PREDICTION_CONFLICT','La evaluación concurrente requiere reintento.')
    if created:
        db.add(AuditEvent(actor_id=actor_id,entity_type='PREDICTION',entity_id=row.id,action='PREDICTION_CREATED',
            request_id=request_id,payload={'snapshot_id':str(snapshot.id),'model_id':str(model.id)}))
        db.flush()
    return row,created


def infer_selected(db, user, period, as_of, model, bundle, request_id):
    """Núcleo usado por el servicio y probado con objetos/artefactos aislados."""
    from app.ml.features import Observation
    from app.ml.predict import predict_snapshot
    if (bundle.manifest['dataset_hash'] != model.dataset_hash or bundle.manifest['algorithm'] != model.algorithm
            or bundle.config.schema_version != model.feature_schema_version
            or bundle.config.criterion_version != model.reference_criterion_version
            or bundle.manifest['data_origin'] != model.data_origin or model.data_origin != period.data_origin):
        raise AppError(409,'MODEL_INCOMPATIBLE','El modelo y su artefacto no son compatibles.')
    selected = repository.select_snapshots(db,period.id,as_of)
    created = reused = 0
    abstentions = []
    for row in selected:
        observation = Observation(student_key=str(row['student_id']),snapshot_id=row['id'],
            enrollment_id=row['enrollment_id'],period_id=period.id,data_origin=row['data_origin'],
            schema_version=row['schema_version'],revision=row['revision'],supersedes_id=row['supersedes_id'],
            window_start=row['window_start'],available_at=row['available_at'],cutoff_at=row['cutoff_at'],
            target_date=row['target_date'],created_at=row['created_at'],
            eligible=bool(row['student_active'] and row['eligible_for_processing'] and
                (row['data_origin']=='SYNTHETIC' or(row['consent_documented'] and row['assent_documented']))),
            values={name:float(row[name]) if row[name] is not None else None for name in bundle.config.features},
            feature_available_at={name:row['available_at'] for name in bundle.config.features},
            input_provenance='snapshot:'+str(row['id']))
        result = predict_snapshot(observation,bundle)
        if result.status != 'EVALUATED':
            abstentions.append(schemas.Abstention(snapshot_id=row['id'],status=result.status,reason=result.reason))
            continue
        _,is_new = persist_evaluated(db,snapshot_id=row['id'],model_id=model.id,result=result,
                                    actor_id=user.id,request_id=request_id)
        created += is_new
        reused += not is_new
    return schemas.PredictionRunResult(period_id=period.id,as_of=as_of,model_id=model.id,
        selected=len(selected),created=created,reused=reused,abstentions=abstentions)


def run_period(db,user,payload,settings,request_id):
    require_admin(user)
    from app.services.synthetic_study import validate_registered
    from app.models.synthetic import SyntheticStudyRecord
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==payload.period_id).with_for_update(read=True))
    if period is None:
        raise AppError(404,'PERIOD_NOT_FOUND','El periodo no está disponible.')
    if period.data_origin!='SYNTHETIC':
        require_ml_protocol()
    if period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado.')
    if payload.as_of > datetime.now(UTC):
        raise AppError(422,'AS_OF_IN_FUTURE','as_of no puede estar en el futuro.')
    study=db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id==period.id))
    if study is None:
        raise AppError(422,'SYNTHETIC_STUDY_NOT_PREPARED','El estudio sintético no está preparado.')
    validate_registered(db,settings,study)
    model = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True),ModelVersion.status=='APPROVED',
                        ModelVersion.data_origin==period.data_origin,ModelVersion.study_id==study.id,
                        ModelVersion.created_at<=payload.as_of))
    if model is None or settings.ml_storage_dir is None:
        raise AppError(409,'MODEL_NOT_AVAILABLE','Modelo no disponible.')
    from app.ml.artifacts import ArtifactStore
    from app.ml.features import MLDiagnostic
    try:
        from app.services.synthetic_study import compatible_model
        compatible_model(settings,study,model)
        bundle = ArtifactStore(settings.ml_storage_dir).load(model.artifact_key)
        # Solo simulación registrada; una firma nunca habilita REAL.
        if (bundle.manifest['scope']!='SYNTHETIC_STUDY' or str(bundle.manifest['study_id'])!=str(study.id)
            or model.manifest.get('approval_kind')!='TECHNICAL_SIMULATION'):
            raise MLDiagnostic('MODEL_NOT_APPROVED')
        if bundle.manifest['artifact_sha256'] != model.artifact_sha256 or bundle.manifest['dataset_hash'] != model.dataset_hash:
            raise MLDiagnostic('MODEL_HASH_MISMATCH')
    except MLDiagnostic:
        raise AppError(409,'MODEL_NOT_AVAILABLE','Modelo no disponible o incompatible.') from None
    try:
        result = infer_selected(db,user,period,payload.as_of,model,bundle,request_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
