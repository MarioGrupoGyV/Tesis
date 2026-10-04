"""Estudio controlado: procedencia privada, actor verificado y operaciones explícitas."""
import base64
import csv
from datetime import date
import hashlib
import io
import json
from uuid import UUID, uuid4, uuid5
from sqlalchemy import select
from app.core.errors import AppError
from app.core.study_storage import StudyStorage
from app.models.s1 import AcademicPeriod, AppUser, AuditEvent, GradeSection
from app.models.s2 import ImportBatchRecord, SnapshotRecord, EnrollmentRecord, StudentRecord
from app.models.synthetic import SyntheticStudyRecord
from app.models.ml import ModelVersion
from app.repositories.imports import advisory_lock


def require_admin(user):
    if user.role!='ADMIN' or not user.is_active:
        raise AppError(403,'FORBIDDEN','Se requiere un administrador activo autenticado.')


def event(db,user,study,action,request_id,**payload):
    db.add(AuditEvent(actor_id=user.id,entity_type='SYNTHETIC_STUDY',entity_id=study.id,
        action=action,request_id=request_id,payload={'data_origin':'SYNTHETIC',**payload}))


def get_study(db,study_id,lock=False):
    if lock:
        # Mismo orden que commit: periodo antes de procedencia. Evita que la
        # comparación mantenga el estudio mientras espera el periodo importado.
        reference=db.get(SyntheticStudyRecord,study_id)
        if reference is None:
            raise AppError(404,'SYNTHETIC_STUDY_NOT_FOUND','El estudio sintético no está disponible.')
        db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==reference.period_id).with_for_update(read=True))
    q=select(SyntheticStudyRecord).where(SyntheticStudyRecord.id==study_id)
    if lock:
        q=q.with_for_update().execution_options(populate_existing=True)
    study=db.scalar(q)
    if study is None:
        raise AppError(404,'SYNTHETIC_STUDY_NOT_FOUND','El estudio sintético no está disponible.')
    return study


def writable_study(db,study):
    period=db.scalar(select(AcademicPeriod).where(AcademicPeriod.id==study.period_id).with_for_update(read=True))
    if period is None or period.data_origin!='SYNTHETIC':
        raise AppError(409,'STUDY_INTEGRITY_ERROR','El contexto del estudio es incompatible.')
    if period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado.')


def validate_registered(db,settings,study):
    from app.ml.synthetic import SyntheticStudyConfig
    config=SyntheticStudyConfig.model_validate(study.config)
    period=db.get(AcademicPeriod,study.period_id)
    if study.data_origin!='SYNTHETIC' or study.generator_version!=config.generator_version or not period or period.data_origin!='SYNTHETIC':
        raise AppError(409,'STUDY_INTEGRITY_ERROR','Origen o contexto del estudio incompatible.')
    payload=StudyStorage(settings.ml_storage_dir).read(study.storage_key,study.payload_sha256)
    content=base64.b64decode(payload['csv_base64'],validate=True)
    if (hashlib.sha256(content).hexdigest()!=study.csv_sha256 or payload['config']!=study.config
        or payload['manifest']!=study.manifest or str(payload['study_id'])!=str(study.id)):
        raise AppError(409,'STUDY_INTEGRITY_ERROR','Procedencia del estudio incompatible.')
    from app.ml.synthetic import canonical
    if (hashlib.sha256(canonical(study.config)).hexdigest()!=study.manifest['config_hash']
        or hashlib.sha256(canonical(payload['labels'])).hexdigest()!=study.manifest['labels_sha256']
        or period.start_date!=config.period_start or period.end_date!=config.period_end
        or period.school_year!=config.school_year):
        raise AppError(409,'STUDY_INTEGRITY_ERROR','Configuración, resultados o calendario incompatibles.')
    return config,payload,content


def verified_csv(db,settings,period,content):
    if period.data_origin!='SYNTHETIC':
        from app.services.processing_policy import require_processing_protocol
        require_processing_protocol()
    study=db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id==period.id))
    if study is None or hashlib.sha256(content).hexdigest()!=study.csv_sha256:
        raise AppError(422,'UNREGISTERED_SYNTHETIC_FILE','Usa el CSV exacto registrado por el generador local para este periodo. No se guardó el archivo.')
    _,_,registered=validate_registered(db,settings,study)
    if registered!=content:
        raise AppError(409,'STUDY_INTEGRITY_ERROR','El archivo no coincide con su procedencia privada.')
    return study


def prepare(db,user,settings,config,seed,tutor_id,request_id):
    require_admin(user)
    from app.ml.synthetic import generate
    generated=generate(config,seed)
    advisory_lock(db,'synthetic-study:'+str(generated.study_id))
    existing=db.get(SyntheticStudyRecord,generated.study_id)
    if existing:
        validate_registered(db,settings,existing)
        return existing,True
    tutor=db.get(AppUser,tutor_id) if tutor_id else None
    if tutor_id and (tutor is None or tutor.role!='TUTOR' or not tutor.is_active):
        raise AppError(422,'INVALID_TUTOR','Indica un tutor activo para la sección sintética propia.')
    rows=list(csv.DictReader(io.StringIO(generated.csv_bytes.decode('utf-8'))))
    # Calendario explícito del protocolo; valores fuera de él se rechazan en importer.
    start=config.period_start
    end=config.period_end
    if db.get(AcademicPeriod,generated.period_id):
        raise AppError(409,'STUDY_CONTEXT_CONFLICT','El contexto ya pertenece a otra preparación.')
    period=AcademicPeriod(id=generated.period_id,code='SYN-'+generated.study_id.hex[:12],
        school_year=start.year,start_date=start,end_date=end,data_origin='SYNTHETIC',is_locked=False)
    db.add(period)
    # El catálogo no tiene origen: nombres internos exclusivos separan el contexto.
    for index,(grade,code) in enumerate(sorted({(int(r['grade']),r['section']) for r in rows})):
        section=db.scalar(select(GradeSection).where(GradeSection.school_year==start.year,
            GradeSection.grade==grade,GradeSection.code==code))
        if section:
            raise AppError(409,'STUDY_CONTEXT_CONFLICT','La sección sintética ya existe en otro contexto.')
        db.add(GradeSection(id=uuid5(generated.study_id,f'section:{grade}:{code}'),grade=grade,code=code,
            school_year=start.year,tutor_id=tutor_id if index==0 else None))
    payload={'study_id':str(generated.study_id),'config':generated.config_json,'manifest':generated.manifest_json,
        'csv_base64':base64.b64encode(generated.csv_bytes).decode(),
        'dataset':generated.dataset.model_dump(mode='json'),'labels':generated.labels_json}
    key=generated.study_id.hex+'.json'
    digest=StudyStorage(settings.ml_storage_dir).write(key,payload)
    study=SyntheticStudyRecord(id=generated.study_id,period_id=generated.period_id,data_origin='SYNTHETIC',
        generator_version=config.generator_version,seed=seed,config=generated.config_json,manifest=generated.manifest_json,
        csv_sha256=hashlib.sha256(generated.csv_bytes).hexdigest(),storage_key=key,payload_sha256=digest,
        created_by=user.id,bindings=[],comparison=None)
    try:
        db.flush()
        db.add(study); db.flush()
        event(db,user,study,'SYNTHETIC_STUDY_PREPARED',request_id,students=config.student_count,observations=len(rows),seed=seed)
        db.commit()
        return study,False
    except Exception:
        db.rollback()
        # El payload huérfano privado es determinista; reintentar verifica sus bytes.
        raise


def bind_imported(db,study,batch,rows,settings):
    _,payload,_=validate_registered(db,settings,study)
    outcomes={r['source_row_number']:r for r in payload['labels']['outcomes']}
    records=db.execute(select(SnapshotRecord,EnrollmentRecord,StudentRecord)
        .join(EnrollmentRecord,EnrollmentRecord.id==SnapshotRecord.enrollment_id)
        .join(StudentRecord,StudentRecord.id==EnrollmentRecord.student_id)
        .where(SnapshotRecord.import_batch_id==batch.id)).all()
    by_key={(s.anon_code,sn.cutoff_at):(sn,e,s) for sn,e,s in records}
    bindings=[]
    for row in rows:
        found=by_key.get((row['student_code'],row['cutoff_at']))
        if found is None:
            raise AppError(409,'STUDY_BINDING_CONFLICT','No se pudo vincular el corte al archivo registrado.')
        sn,_,_=found
        outcome=outcomes.get(row['source_row_number'])
        if outcome is None or outcome['student_code']!=row['student_code'] or outcome['cutoff_at']!=row['cutoff_at'].isoformat() or outcome['revision']!=sn.revision:
            raise AppError(409,'STUDY_BINDING_CONFLICT','El resultado futuro no está vinculado al corte registrado.')
        if sn.row_sha256!=row['row_sha256'] or sn.data_origin!='SYNTHETIC' or sn.revision!=1:
            raise AppError(409,'STUDY_BINDING_CONFLICT','La evidencia importada no coincide con el estudio.')
        bindings.append({'snapshot_id':str(sn.id),'student_code':row['student_code'],
            'cutoff_at':row['cutoff_at'].isoformat(),'source_row_number':row['source_row_number'],
            'row_sha256':row['row_sha256'],'revision':sn.revision,
            'generated_snapshot_id':outcome['snapshot_id']})
    study.bindings=bindings
    db.flush()


def comparison_safe(report):
    # Nunca serializar estudiantes, índices, predicciones privadas o etiquetas.
    forbidden={'student_keys','students','train_students','validation_students','external_students',
               'development_students','partitions','validation_predictions','external_predictions','row_indices',
               'train_indices','validation_indices','excluded_indices','indices','student_key','snapshot_id',
               'student_code','outcomes','labels','external_indices','development_indices','protocol'}
    if isinstance(report,dict):
        return {k:comparison_safe(v) for k,v in report.items() if k not in forbidden}
    if isinstance(report,list):
        return [comparison_safe(v) for v in report]
    return report


def public_generation(manifest):
    keys=('version','generator_version','scope','data_origin','study_id','period_id','seed','config_hash',
          'csv_sha256','dataset_sha256','labels_sha256','student_count','observation_count',
          'eligible_observation_count','context','limits')
    return {k:manifest[k] for k in keys}


def selected_artifact(settings,study):
    from app.ml.artifacts import ArtifactStore
    from app.ml.synthetic import SyntheticStudyConfig
    if not study.comparison or not study.bindings:
        raise AppError(409,'SYNTHETIC_COMPARISON_REQUIRED','Compara primero los modelos del estudio importado.')
    algorithm=study.comparison['selected_algorithm']
    key=study.comparison['artifact_keys'][algorithm]
    manifest,_,_=ArtifactStore(settings.ml_storage_dir).inspect(key)
    config=SyntheticStudyConfig.model_validate(study.config)
    if (manifest['scope']!='SYNTHETIC_STUDY' or manifest['data_origin']!='SYNTHETIC'
        or str(manifest['study_id'])!=str(study.id) or manifest['algorithm']!=algorithm
        or manifest['feature_schema']!=config.features.model_dump(mode='json')
        or manifest.get('generator_version')!=study.generator_version
        or manifest.get('synthetic_config_hash')!=study.manifest['config_hash']
        or manifest.get('seed')!=study.seed
        or manifest.get('synthetic_evaluation',{}).get('source_dataset_hash')!=study.manifest['dataset_sha256']):
        raise AppError(409,'MODEL_INCOMPATIBLE','El artefacto no cumple la procedencia y compatibilidad del estudio.')
    return manifest,key


def compatible_model(settings,study,model):
    manifest,key=selected_artifact(settings,study)
    from app.ml.synthetic import SyntheticStudyConfig
    config=SyntheticStudyConfig.model_validate(study.config)
    if (not study.comparison or not study.bindings or model.status!='APPROVED' or model.data_origin!='SYNTHETIC'
        or model.algorithm!=study.comparison['selected_algorithm']
        or key!=model.artifact_key
        or manifest['scope']!='SYNTHETIC_STUDY' or manifest['data_origin']!='SYNTHETIC'
        or str(manifest['study_id'])!=str(study.id) or model.study_id!=study.id
        or manifest['algorithm']!=model.algorithm or manifest['dataset_hash']!=model.dataset_hash
        or manifest['artifact_sha256']!=model.artifact_sha256 or manifest['feature_schema']!=config.features.model_dump(mode='json')
        or manifest['feature_schema']['schema_version']!=model.feature_schema_version
        or manifest['reference_criterion_version']!=model.reference_criterion_version
        or manifest.get('generator_version')!=study.generator_version or manifest.get('synthetic_config_hash')!=study.manifest['config_hash']
        or manifest.get('seed')!=study.seed or manifest.get('synthetic_evaluation',{}).get('source_dataset_hash')!=study.manifest['dataset_sha256']
        or model.manifest!={**manifest,'approval_kind':'TECHNICAL_SIMULATION'}
        or model.parameters!=manifest['parameters'] or model.metrics!=manifest['metrics']):
        raise AppError(409,'MODEL_INCOMPATIBLE','El modelo no cumple la procedencia y compatibilidad del estudio.')
    return manifest


def compare_registered(db,user,settings,study_id,request_id):
    require_admin(user)
    study=get_study(db,study_id,lock=True)
    writable_study(db,study)
    config,payload,_=validate_registered(db,settings,study)
    if not study.bindings:
        raise AppError(409,'SYNTHETIC_IMPORT_REQUIRED','Confirma primero el CSV registrado mediante la API.')
    from app.ml.features import Dataset
    from app.ml.train import compare_study
    from app.ml.artifacts import ArtifactStore
    if study.comparison:
        # Reutilización verifica los cuatro artefactos; no vuelve a entrenar.
        for key in study.comparison['artifact_keys'].values():
            ArtifactStore(settings.ml_storage_dir).inspect(key)
        return {**comparison_safe(study.comparison['report']),'reused':True}
    dataset=Dataset.model_validate(payload['dataset'])
    if hashlib.sha256(dataset.model_dump_json().encode()).hexdigest()!=study.manifest['dataset_sha256']:
        raise AppError(409,'STUDY_INTEGRITY_ERROR','El dataset no coincide con la generación registrada.')
    if len(study.bindings)!=len(dataset.observations):
        raise AppError(409,'STUDY_BINDING_CONFLICT','El estudio no tiene todos sus cortes vinculados.')
    comparison=compare_study(dataset,config)
    store=ArtifactStore(settings.ml_storage_dir)
    keys={algorithm:store.save(bundle,comparison.training_dataset) for algorithm,bundle in comparison.bundles.items()}
    study.comparison={'artifact_keys':keys,'report':comparison.report,'selected_algorithm':comparison.selected_algorithm}
    event(db,user,study,'SYNTHETIC_MODELS_COMPARED',request_id,algorithms=list(keys),selected_algorithm=comparison.selected_algorithm)
    db.commit()
    return {**comparison_safe(comparison.report),'reused':False}


def register_model(db,user,settings,study_id,algorithm,request_id):
    require_admin(user)
    study=get_study(db,study_id,lock=True)
    writable_study(db,study)
    config,_,_=validate_registered(db,settings,study)
    if not study.comparison or not study.bindings:
        raise AppError(409,'SYNTHETIC_COMPARISON_REQUIRED','Compara primero los modelos del estudio importado.')
    algorithm=algorithm or study.comparison['selected_algorithm']
    if algorithm!=study.comparison['selected_algorithm']:
        raise AppError(422,'MODEL_NOT_SELECTED','Registra únicamente el algoritmo seleccionado en desarrollo antes de evaluar la reserva.')
    key=study.comparison['artifact_keys'].get(algorithm)
    if key is None:
        raise AppError(422,'ALGORITHM_NOT_COMPARABLE','El algoritmo no tiene comparación registrada.')
    manifest,key=selected_artifact(settings,study)
    if (manifest['scope']!='SYNTHETIC_STUDY' or manifest['data_origin']!='SYNTHETIC' or str(manifest['study_id'])!=str(study.id)
        or manifest['algorithm']!=algorithm or manifest['feature_schema']!=config.features.model_dump(mode='json')):
        raise AppError(409,'MODEL_INCOMPATIBLE','El artefacto no pertenece al estudio registrado.')
    record=db.scalar(select(ModelVersion).where(ModelVersion.study_id==study.id,ModelVersion.algorithm==algorithm))
    if record:
        compatible_model(settings,study,record)
        return record,True
    record=ModelVersion(id=uuid4(),study_id=study.id,name='Estudio sintético '+algorithm,
        version=study.id.hex,data_origin='SYNTHETIC',algorithm=algorithm,dataset_hash=manifest['dataset_hash'],
        artifact_sha256=manifest['artifact_sha256'],artifact_key=key,feature_schema_version=manifest['feature_schema']['schema_version'],
        reference_criterion_version=manifest['reference_criterion_version'],status='APPROVED',is_active=False,
        parameters=manifest['parameters'],metrics=manifest['metrics'],
        manifest={**manifest,'approval_kind':'TECHNICAL_SIMULATION'},created_by=user.id)
    compatible_model(settings,study,record)
    db.add(record); db.flush()
    event(db,user,study,'SYNTHETIC_MODEL_REGISTERED',request_id,model_id=str(record.id),algorithm=algorithm,
        approval_kind='TECHNICAL_SIMULATION')
    db.commit()
    return record,False


def activate_model(db,user,settings,model_id,request_id):
    require_admin(user)
    advisory_lock(db,'active-model:SYNTHETIC')
    model=db.scalar(select(ModelVersion).where(ModelVersion.id==model_id).with_for_update())
    if model is None:
        raise AppError(404,'MODEL_NOT_FOUND','El modelo no está disponible.')
    if model.data_origin!='SYNTHETIC':
        from app.services.processing_policy import require_ml_protocol
        require_ml_protocol()
    study=get_study(db,model.study_id,lock=True)
    writable_study(db,study)
    validate_registered(db,settings,study)
    if not study.comparison or not study.bindings or model.status!='APPROVED':
        raise AppError(409,'MODEL_INCOMPATIBLE','La aprobación técnica de simulación está incompleta.')
    compatible_model(settings,study,model)
    from app.ml.artifacts import ArtifactStore
    ArtifactStore(settings.ml_storage_dir).load(model.artifact_key)
    if model.is_active:
        return model,True
    try:
        for current in db.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True),ModelVersion.data_origin=='SYNTHETIC').with_for_update()):
            current.is_active=False
        db.flush()
        model.is_active=True
        event(db,user,study,'SYNTHETIC_MODEL_ACTIVATED',request_id,model_id=str(model.id),approval_kind='TECHNICAL_SIMULATION')
        db.commit()
        return model,False
    except Exception:
        db.rollback(); raise
