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
from app.schemas.s5 import FollowupResult
from app.schemas.s2 import Prediction
from app.services.simulated_clock import simulated_instant
from app.services.processing_policy import require_ml_protocol, require_study, study_for_period
from app.services.processing_protocol import protocol_confirms_period, real_student_processable
from app.services.students import projection


def require_admin(user):
    if user.role != 'ADMIN':
        raise AppError(403,'FORBIDDEN','Solo el administrador puede consultar modelos o solicitar inferencia.')


def public_model(db,row):
    """Modelo con alcance, tipo de aprobación y advertencias de n pequeño (REAL: solo exploratorio local)."""
    from app.models.synthetic import SyntheticStudyRecord
    manifest = row.manifest or {}
    warnings = []
    if row.data_origin == 'REAL' and row.study_id is not None:
        study = db.get(SyntheticStudyRecord,row.study_id)
        warnings = list(((study.comparison or {}).get('report') or {}).get('warnings') or []) if study else []
    return schemas.Model.model_validate({**{k:getattr(row,k) for k in ('id','name','version','algorithm','data_origin',
        'feature_schema_version','reference_criterion_version','status','is_active','created_at')},
        'scope':manifest.get('scope'),'approval_kind':manifest.get('approval_kind'),'warnings':warnings})


def list_models(db,user,page,page_size):
    require_admin(user)
    rows,total = repository.models(db,page,page_size)
    return schemas.ModelPage(items=[public_model(db,r) for r in rows],total=total,page=page,page_size=page_size)


def model_detail(db,user,id):
    require_admin(user)
    row = db.get(ModelVersion,id)
    if row is None or row.data_origin not in ('REAL','SYNTHETIC'):
        raise AppError(404,'MODEL_NOT_FOUND','El modelo no está disponible.')
    return public_model(db,row)


def prediction_detail(db,user,id):
    if user.role not in ('ADMIN','TUTOR','DIRECTOR'):
        raise AppError(403,'FORBIDDEN','No tienes acceso a predicciones.')
    row = repository.accessible_prediction(db,user,id)
    if row is None:
        # Igual para UUID inexistente o sección ajena: no permite enumerar casos.
        raise AppError(404,'PREDICTION_NOT_FOUND','La predicción no está disponible.')
    return projection(Prediction,selected_prediction(db,row.id))


def persist_evaluated(db, *, snapshot_id, model_id, result, actor_id, request_id, as_of=None):
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
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==snapshot.period_id).with_for_update(read=True)
                       .execution_options(populate_existing=True))
    if period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado.')
    enrollment = db.get(EnrollmentRecord,snapshot.enrollment_id)
    student = db.get(StudentRecord,enrollment.student_id)
    if not real_student_processable(data_origin=student.data_origin,is_active=student.is_active,
            eligible_flag=student.eligible_for_processing,consent_documented=student.consent_documented,
            assent_documented=student.assent_documented,
            protocol_confirmed_for_enrollment=protocol_confirms_period(db,snapshot.period_id)):
        raise AppError(422,'NOT_ELIGIBLE','El corte no es elegible para inferencia.')
    if snapshot.data_origin != model.data_origin or snapshot.data_origin not in ('REAL','SYNTHETIC'):
        raise AppError(422,'ORIGIN_NOT_SUPPORTED','Corte y modelo deben conservar el mismo origen.')
    # La persistencia aislada prueba integridad con modelos inactivos. La selección
    # operativa exige protocolo + modelo aprobado/activo en run_period, sin bypass.
    manual = snapshot.entry_channel == 'MANUAL' and snapshot.schema_version == 'manual-v1'
    if manual and (period.data_origin != 'SYNTHETIC' or snapshot.data_origin != 'SYNTHETIC'):
        raise AppError(422,'INSTITUTIONAL_PROCESSING_NOT_READY','La evaluación de mediciones manuales solo está disponible en simulación.')
    if model.feature_schema_version != 'ml-features-v1' or (snapshot.schema_version != 'academic-v1' and not manual):
        raise AppError(409,'MODEL_INCOMPATIBLE','El esquema del modelo no es compatible.')
    row,created = repository.insert_prediction(db,dict(id=uuid4(),enrollment_id=snapshot.enrollment_id,
        snapshot_id=snapshot.id,model_id=model.id,data_origin=snapshot.data_origin,risk_level=result.risk_level,
        probabilities_calibrated=False,probability_low=None,probability_medium=None,probability_high=None,
        as_of_at=simulated_instant(as_of)))
    if row is None:
        raise AppError(409,'PREDICTION_CONFLICT','La evaluación concurrente requiere reintento.')
    if created:
        db.add(AuditEvent(actor_id=actor_id,entity_type='PREDICTION',entity_id=row.id,action='PREDICTION_CREATED',
            request_id=request_id,payload={'snapshot_id':str(snapshot.id),'model_id':str(model.id)}))
        db.flush()
    return row,created


def observation_from_row(row, period, bundle):
    """Observación del modelo. manual-v1 equivale semánticamente a academic-v1 (mismas cinco variables).

    En MANUAL no existe fecha objetivo observada: el horizonte del modelo se deriva solo en
    memoria (día de corte en America/Lima + horizon_days) y nunca se guarda en el corte.
    """
    from datetime import timedelta
    from app.ml.features import LIMA, Observation
    manual = row.get('entry_channel') == 'MANUAL'
    available = {name:row['available_at'] for name in bundle.config.features}
    target = row['target_date']
    if manual:
        stored = row.get('variable_available_at') or {}
        for name in bundle.config.features:
            if name in stored:
                available[name] = datetime.fromisoformat(stored[name])
        target = row['cutoff_at'].astimezone(LIMA).date() + timedelta(days=bundle.config.horizon_days)
    return Observation(student_key=str(row['student_id']),snapshot_id=row['id'],
        enrollment_id=row['enrollment_id'],period_id=period.id,data_origin=row['data_origin'],
        schema_version='academic-v1',revision=row['revision'],supersedes_id=row['supersedes_id'],
        window_start=row['window_start'],available_at=row['available_at'],cutoff_at=row['cutoff_at'],
        target_date=target,created_at=row['created_at'],
        eligible=real_student_processable(data_origin=row['data_origin'],is_active=bool(row['student_active']),
            eligible_flag=bool(row['eligible_for_processing']),consent_documented=bool(row['consent_documented']),
            assent_documented=bool(row['assent_documented']),
            protocol_confirmed_for_enrollment=bool(row.get('protocol_confirmed'))),
        values={name:float(row[name]) if row[name] is not None else None for name in bundle.config.features},
        feature_available_at=available,input_provenance='snapshot:'+str(row['id']))


def infer_selected(db, user, period, as_of, model, bundle, request_id):
    """Núcleo usado por el servicio y probado con objetos/artefactos aislados."""
    from app.ml.features import Observation
    from app.ml.predict import predict_snapshot
    if (bundle.manifest['dataset_hash'] != model.dataset_hash or bundle.manifest['algorithm'] != model.algorithm
            or bundle.config.schema_version != model.feature_schema_version
            or bundle.config.criterion_version != model.reference_criterion_version
            or bundle.manifest['data_origin'] != model.data_origin or model.data_origin != period.data_origin):
        raise AppError(409,'MODEL_INCOMPATIBLE','El modelo y su artefacto no son compatibles.')
    selected = repository.select_snapshots(db,period.id,as_of,strict_incorporation=period.data_origin=='SYNTHETIC')
    created = reused = 0
    abstentions = []
    for row in selected:
        if row.get('entry_channel')=='MANUAL' and period.data_origin!='SYNTHETIC':
            # Las mediciones manuales REAL (M1) no se evalúan: no hay fecha objetivo observada ni cierre de referencia.
            abstentions.append(schemas.Abstention(snapshot_id=row['id'],status='INELIGIBLE',reason='MANUAL_REAL_NOT_EVALUABLE'))
            continue
        observation = observation_from_row(row,period,bundle)
        result = predict_snapshot(observation,bundle)
        if result.status != 'EVALUATED':
            abstentions.append(schemas.Abstention(snapshot_id=row['id'],status=result.status,reason=result.reason))
            continue
        _,is_new = persist_evaluated(db,snapshot_id=row['id'],model_id=model.id,result=result,
                                    actor_id=user.id,request_id=request_id,as_of=as_of)
        created += is_new
        reused += not is_new
    return schemas.PredictionRunResult(period_id=period.id,as_of=as_of,model_id=model.id,
        selected=len(selected),created=created,reused=reused,abstentions=abstentions,
        followup=FollowupResult(period_id=period.id))


APPROVAL_BY_ORIGIN = {'SYNTHETIC':('SYNTHETIC_STUDY','TECHNICAL_SIMULATION'),'REAL':('INSTITUTIONAL_STUDY','LOCAL_EXPLORATORY')}


def load_active_model(db,period,settings,as_of):
    """Estudio del origen del periodo (REAL exige protocolo confirmado) + modelo activo aprobado + artefacto verificado."""
    from app.services.synthetic_study import compatible_model, validate_registered
    study,_ = study_for_period(db,period)
    require_study(study,period)
    validate_registered(db,settings,study)
    model = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True),ModelVersion.status=='APPROVED',
                        ModelVersion.data_origin==period.data_origin,ModelVersion.study_id==study.id,
                        ModelVersion.created_at<=(as_of if period.data_origin=='SYNTHETIC' else datetime.now(UTC))).with_for_update(read=True)
                        .execution_options(populate_existing=True))
    if model is None or settings.ml_storage_dir is None:
        raise AppError(409,'MODEL_NOT_AVAILABLE','Modelo no disponible.')
    from app.ml.artifacts import ArtifactStore
    from app.ml.features import MLDiagnostic
    scope,approval = APPROVAL_BY_ORIGIN[period.data_origin]
    try:
        compatible_model(settings,study,model)
        bundle = ArtifactStore(settings.ml_storage_dir).load(model.artifact_key)
        # Un modelo solo evalúa su propio origen y alcance; una firma nunca habilita otro.
        if (bundle.manifest['scope']!=scope or str(bundle.manifest['study_id'])!=str(study.id)
            or model.manifest.get('approval_kind')!=approval):
            raise MLDiagnostic('MODEL_NOT_APPROVED')
        if bundle.manifest['artifact_sha256'] != model.artifact_sha256 or bundle.manifest['dataset_hash'] != model.dataset_hash:
            raise MLDiagnostic('MODEL_HASH_MISMATCH')
    except MLDiagnostic:
        raise AppError(409,'MODEL_NOT_AVAILABLE','Modelo no disponible o incompatible.') from None
    return study,model,bundle


def run_period(db,user,payload,settings,request_id):
    require_admin(user)
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==payload.period_id).with_for_update(read=True)
                       .execution_options(populate_existing=True))
    if period is None:
        raise AppError(404,'PERIOD_NOT_FOUND','El periodo no está disponible.')
    study_for_period(db,period)  # REAL: sin protocolo confirmado → INSTITUTIONAL_PROCESSING_NOT_READY
    if period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado.')
    if payload.as_of > datetime.now(UTC):
        raise AppError(422,'AS_OF_IN_FUTURE','as_of no puede estar en el futuro.')
    study,model,bundle = load_active_model(db,period,settings,payload.as_of)
    try:
        # Orden común S5: periodo compartido → modelo compartido → matrículas UUID.
        # Importación toma las mismas matrículas antes de insertar otra revisión.
        # Seleccionar después de los locks evita evaluar una revisión ya reemplazada.
        db.scalars(select(EnrollmentRecord).where(EnrollmentRecord.period_id==period.id)
            .order_by(EnrollmentRecord.id).with_for_update()
            .execution_options(populate_existing=True)).all()
        result = infer_selected(db,user,period,payload.as_of,model,bundle,request_id)
        from app.services.followup import sync_current
        # Solo predicciones elegidas por as_of; sync descarta aquellas que ya no
        # coinciden con la revisión/modelo actuales. Sin commit intermedio.
        chosen = repository.select_snapshots(db,period.id,payload.as_of,strict_incorporation=period.data_origin=='SYNTHETIC')
        prediction_ids = db.scalars(select(PredictionRecord.id).where(
            PredictionRecord.model_id==model.id,
            PredictionRecord.snapshot_id.in_([row['id'] for row in chosen]))).all()
        result.followup = sync_current(db,user,period.id,settings,request_id,
                                     prediction_ids=prediction_ids,as_of=payload.as_of)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


LABELS = {'average_grade':'promedio','attendance_pct':'asistencia','activities_pct':'actividades',
          'participation_level':'participación','behavior_incidents':'incidencias'}


def out_of_model_scale(observation, config):
    """Mensajes para valores que el modelo activo no admite; solo informa, no cambia la inferencia."""
    problems = []
    for name, value in observation.values.items():
        if value is None:
            continue
        scale = config.scales[name]
        if not scale.minimum <= value <= scale.maximum:
            problems.append(f'{LABELS.get(name,name)} {value:g} (el modelo admite {scale.minimum:g}–{scale.maximum:g})')
        elif name == 'participation_level' and value not in config.participation_values:
            problems.append(f'participación {value:g} (el modelo admite {", ".join(str(v) for v in config.participation_values)})')
    return problems


def evaluate_student(db,user,student_id,period_id,settings,request_id):
    """Evalúa solo la última revisión de la matrícula y sincroniza su seguimiento; un solo commit."""
    require_admin(user)
    from sqlalchemy.exc import IntegrityError
    from app.services.students import authorize_student
    enrollment = authorize_student(db,user,student_id,period_id)
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==period_id).with_for_update(read=True)
                       .execution_options(populate_existing=True))
    study_for_period(db,period)
    if period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado.')
    now = datetime.now(UTC)
    try:
        study,model,bundle = load_active_model(db,period,settings,now)
        db.get(EnrollmentRecord,enrollment.id,with_for_update=True,populate_existing=True)
        rows = repository.select_snapshots(db,period.id,now,enrollment.id,strict_incorporation=period.data_origin=='SYNTHETIC')
        if not rows:
            raise AppError(422,'NO_MEASUREMENT','Registra una medición antes de evaluar al estudiante.')
        row = rows[0]
        from app.ml.predict import predict_snapshot
        observation = observation_from_row(row,period,bundle)
        outside = out_of_model_scale(observation,bundle.config)
        if outside:
            raise AppError(422,'MEASUREMENT_OUT_OF_MODEL_SCALE',
                'La medición tiene valores fuera de la escala del modelo activo: '+'; '.join(outside)+
                '. Corrige la medición (se crea una revisión) y evalúa de nuevo. No se asignó riesgo.')
        result = predict_snapshot(observation,bundle)
        base = dict(snapshot_id=row['id'])
        if result.status == 'INELIGIBLE':
            out = schemas.StudentEvaluation(status='NOT_ELIGIBLE',reason='El estudiante no está activo o no es elegible para la simulación.',**base)
        elif result.status == 'INSUFFICIENT_DATA':
            out = schemas.StudentEvaluation(status='INSUFFICIENT_DATA',
                reason='Faltan datos para evaluar. No se asigna riesgo.',**base)
        elif result.status != 'EVALUATED':
            raise AppError(409,'MODEL_INCOMPATIBLE','El modelo activo no es compatible con esta medición.')
        else:
            prediction,created = persist_evaluated(db,snapshot_id=row['id'],model_id=model.id,result=result,
                                                   actor_id=user.id,request_id=request_id)
            from app.services.followup import sync_current
            sync_current(db,user,period.id,settings,request_id,prediction_ids=[prediction.id])
            decision = repository.decision_for(db,prediction.id)
            action = 'NONE'
            if decision is not None and decision.alert_id is not None:
                action = {'CREATED':'CREATED','UPDATED':'UPDATED'}.get(decision.decision,'NONE')
                if not created:
                    action = 'REUSED'
            out = schemas.StudentEvaluation(status='EVALUATED',risk_level=prediction.risk_level,
                prediction_id=prediction.id,prediction_reused=not created,case_action=action,
                alert_id=decision.alert_id if decision else None,**base)
        db.add(AuditEvent(actor_id=user.id,entity_type='ENROLLMENT',entity_id=enrollment.id,
            action='STUDENT_EVALUATION_REQUESTED',request_id=request_id,
            payload={'snapshot_id':str(row['id']),'status':out.status,'model_id':str(model.id),
                     'prediction_id':str(out.prediction_id) if out.prediction_id else None}))
        db.commit()
        return out
    except IntegrityError:
        db.rollback()
        raise AppError(409,'EVALUATION_CONFLICT','La evaluación concurrente requiere reintento.') from None
    except Exception:
        db.rollback()
        raise
