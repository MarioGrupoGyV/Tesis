"""Seguimiento de simulación: decisiones persistentes, locks, versiones y auditoría."""
from datetime import UTC, datetime
import hashlib
import json
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.errors import AppError
from app.models.followup import AlertRecord, InterventionRecord, FollowupDecisionRecord
from app.models.ml import ModelVersion
from app.models.s1 import AcademicPeriod, AppUser, AuditEvent
from app.models.s2 import SnapshotRecord
from app.models.synthetic import SyntheticStudyRecord
from app.repositories import followup as repository
from app.repositories.s1 import sections_for_period
from app.repositories import students as students_repository
from app.schemas import s5, s2
from app.services.processing_policy import require_processing_protocol
from app.services.students import projection

POLICY='followup-policy-v1'
ACTIVE=('OPEN','IN_REVIEW')


def require_reader(user):
    if user.role not in ('ADMIN','TUTOR','DIRECTOR'):
        raise AppError(403,'FORBIDDEN','Tu rol no tiene acceso al seguimiento.')


def require_writer(user):
    if user.role not in ('ADMIN','TUTOR'):
        raise AppError(403,'FORBIDDEN','Tu rol no permite modificar seguimiento.')


def require_admin(user):
    if user.role!='ADMIN':
        raise AppError(403,'FORBIDDEN','Solo el administrador puede actualizar alertas del estudio.')


def context_period(db,user,period_id,settings,section_id=None,write=False):
    require_reader(user)
    query=select(AcademicPeriod).where(AcademicPeriod.id==period_id)
    if write:
        query=query.with_for_update(read=True).execution_options(populate_existing=True)
    period=db.scalar(query)
    if period is None:
        raise AppError(404,'PERIOD_NOT_FOUND','El periodo no está disponible.')
    if period.data_origin!='SYNTHETIC':
        require_processing_protocol()
    if write and period.is_locked:
        raise AppError(409,'PERIOD_LOCKED','El periodo está bloqueado y no admite cambios de seguimiento.')
    study=db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id==period.id,
        SyntheticStudyRecord.data_origin=='SYNTHETIC'))
    if study is None:
        raise AppError(422,'SYNTHETIC_STUDY_NOT_PREPARED','El estudio sintético no está preparado.')
    from app.services.synthetic_study import validate_registered
    try:
        validate_registered(db,settings,study)
    except ValueError:
        raise AppError(409,'STUDY_INTEGRITY_ERROR','La configuración o procedencia privada del estudio es incompatible.') from None
    except OSError:
        raise AppError(503,'STUDY_STORAGE_UNAVAILABLE','Almacenamiento del estudio no disponible.') from None
    allowed=sections_for_period(db,period,user.id if user.role=='TUTOR' else None)
    if user.role=='TUTOR' and not allowed:
        raise AppError(403,'FORBIDDEN','No tienes secciones asignadas en este periodo.')
    if section_id is not None and section_id not in {s.id for s in allowed}:
        raise AppError(404,'SECTION_NOT_FOUND','La sección no está disponible en este periodo.')
    return period,study,allowed


def event(db,user,record,entity_type,action,request_id,**payload):
    db.add(AuditEvent(actor_id=user.id,entity_type=entity_type,entity_id=record.id,
        action=action,request_id=request_id,recorded_at=datetime.now(UTC),payload={'data_origin':'SYNTHETIC',
        'enrollment_id':str(record.enrollment_id),**payload}))


def sync_current(db,user,period_id,settings,request_id,prediction_ids=None):
    """Sin commit: el llamador confirma predicción, decisión/caso y auditoría juntos.

    Bloquea periodo/modelo/matrículas antes de decidir. Solo el conjunto actual
    puede cambiar casos; IDs de inferencia histórica se cuentan como ignorados.
    """
    require_admin(user)
    period,study,allowed=context_period(db,user,period_id,settings,write=True)
    model=db.scalar(select(ModelVersion).where(ModelVersion.study_id==study.id,
        ModelVersion.is_active.is_(True),ModelVersion.status=='APPROVED',
        ModelVersion.data_origin=='SYNTHETIC').with_for_update(read=True)
        .execution_options(populate_existing=True))
    if model is None:
        raise AppError(409,'MODEL_NOT_AVAILABLE','Modelo no disponible para actualizar alertas.')
    from app.services.synthetic_study import compatible_model
    try:
        compatible_model(settings,study,model)
    except ValueError:
        raise AppError(409,'MODEL_NOT_AVAILABLE','Modelo no disponible o incompatible para actualizar alertas.') from None
    except OSError:
        raise AppError(503,'MODEL_STORAGE_UNAVAILABLE','Almacenamiento del modelo no disponible.') from None
    repository.lock_enrollments(db,period.id)
    rows=repository.current_rows(db,period.id)
    allowed_ids={section.id for section in allowed}
    if any(row['section_id'] not in allowed_ids for row in rows):
        raise AppError(409,'STUDY_INTEGRITY_ERROR','Una matrícula no pertenece a las secciones del contexto registrado.')
    result=s5.FollowupResult(period_id=period.id)
    requested={str(id) for id in prediction_ids} if prediction_ids is not None else None
    actual={str(row['_prediction_id']) for row in rows if row['_prediction_id'] is not None}
    if requested is not None:
        result.ignored_stale=len(requested-actual)
    for row in rows:
        prediction_id=row['_prediction_id']
        if prediction_id is None:
            result.skipped_missing+=1
            continue
        if requested is not None and str(prediction_id) not in requested:
            continue
        if row['_model_id']!=model.id or row['_study_id']!=study.id or row['_batch_status']!='COMMITTED':
            raise AppError(409,'STUDY_INTEGRITY_ERROR','La evaluación no pertenece al contexto registrado.')
        prior=repository.decision(db,prediction_id)
        if prior:
            result.reused+=1
            continue
        active=repository.active_alert(db,row['enrollment_id'])
        if active:
            source=students_repository.selected_prediction(db,active.prediction_id)
            source_snapshot=db.get(SnapshotRecord,source['snapshot_id'])
            if (source['cutoff_at'],source_snapshot.revision)>(row['latest_cutoff_at'],row['_revision']):
                result.ignored_stale+=1
                continue
        if row['risk_level'] in ('MEDIUM','HIGH'):
            if active is None:
                tutor=db.get(AppUser,row['_tutor_id']) if row['_tutor_id'] else None
                assigned=tutor.id if tutor and tutor.is_active and tutor.role=='TUTOR' else None
                active=AlertRecord(id=uuid4(),enrollment_id=row['enrollment_id'],prediction_id=prediction_id,
                    data_origin='SYNTHETIC',assigned_to=assigned,severity=row['risk_level'],status='OPEN',version=1)
                db.add(active);db.flush()
                decision='CREATED';result.created+=1
                event(db,user,active,'ALERT','ALERT_CREATED',request_id,prediction_id=str(prediction_id),
                    severity=active.severity,status=active.status,version=active.version,policy_version=POLICY)
            else:
                decision='UPDATED'
                if active.prediction_id!=prediction_id or active.severity!=row['risk_level']:
                    previous={'prediction_id':str(active.prediction_id),'severity':active.severity,'version':active.version}
                    active.prediction_id=prediction_id;active.severity=row['risk_level']
                    active.version+=1;active.updated_at=datetime.now(UTC)
                    result.updated+=1
                    event(db,user,active,'ALERT','ALERT_SOURCE_UPDATED',request_id,previous=previous,
                        prediction_id=str(prediction_id),severity=active.severity,status=active.status,
                        version=active.version,policy_version=POLICY)
        elif row['risk_level']=='LOW':
            if active:
                decision='RETAINED_LOW';result.retained_low+=1
                event(db,user,active,'ALERT','ALERT_LOW_RETAINED',request_id,prediction_id=str(prediction_id),
                    status=active.status,version=active.version,policy_version=POLICY)
            else:
                decision='NO_ALERT';result.no_alert+=1
        else:
            raise AppError(409,'FOLLOWUP_INTEGRITY_ERROR','La clase de evaluación no está admitida.')
        record=FollowupDecisionRecord(id=uuid4(),prediction_id=prediction_id,enrollment_id=row['enrollment_id'],
            data_origin='SYNTHETIC',study_id=study.id,alert_id=active.id if active else None,
            decision=decision,policy_version=POLICY,recorded_at=datetime.now(UTC))
        db.add(record)
        db.add(AuditEvent(actor_id=user.id,entity_type='FOLLOWUP_DECISION',entity_id=record.id,
            action='FOLLOWUP_DECISION_RECORDED',request_id=request_id,recorded_at=datetime.now(UTC),payload={
                'data_origin':'SYNTHETIC','prediction_id':str(prediction_id),
                'alert_id':str(active.id) if active else None,'decision':decision,'policy_version':POLICY}))
        db.flush()
    return result


def domain_integrity(exc):
    """Integridad de dominio siempre es 409, jamás un 503 de disponibilidad."""
    return AppError(409,'FOLLOWUP_CONFLICT','El contexto cambió o existe una operación concurrente. Revisa el recurso antes de intentar de nuevo.')


def sync_operation(db,user,period_id,settings,request_id):
    try:
        result=sync_current(db,user,period_id,settings,request_id)
        db.commit();return result
    except IntegrityError as exc:
        db.rollback();raise domain_integrity(exc) from None
    except Exception:
        db.rollback();raise


def capabilities(user,period,status):
    writer=user.role in ('ADMIN','TUTOR')
    reason='ROLE_RESTRICTED' if not writer else 'PERIOD_LOCKED' if period.is_locked else 'ALERT_CLOSED' if status not in ACTIVE else None
    return {'can_edit':reason is None,'can_plan':reason is None,'reason':reason}


def public_case(db,user,row):
    period=db.get(AcademicPeriod,row['period_id'])
    values={key:row[key] for key in s5.AlertCase.model_fields if key!='capabilities'}
    values['capabilities']=capabilities(user,period,row['status'])
    return s5.AlertCase.model_validate(values)


def intervention_view(user,period,record):
    reason='ROLE_RESTRICTED' if user.role not in ('ADMIN','TUTOR') else 'PERIOD_LOCKED' if period.is_locked else 'INTERVENTION_TERMINAL' if record.status!='PLANNED' else None
    values={key:getattr(record,key) for key in s2.Intervention.model_fields}
    return s5.InterventionView.model_validate({**values,'can_edit':reason is None,'edit_block_reason':reason})


def list_alerts(db,user,settings,**filters):
    _,_,allowed=context_period(db,user,filters['period_id'],settings,filters.get('section_id'))
    rows,total=repository.list_alerts(db,user,authorized_section_ids=[section.id for section in allowed],**filters)
    return s5.AlertPage(items=[public_case(db,user,row) for row in rows],total=total,
        page=filters['page'],page_size=filters['page_size'])


def detail(db,user,id,settings):
    require_reader(user)
    row=repository.public_alert(db,user,id)
    if row is None:
        raise AppError(404,'ALERT_NOT_FOUND','El caso no está disponible.')
    period,_,_=context_period(db,user,row['period_id'],settings,row['section_id'])
    snapshot=db.get(SnapshotRecord,row['_snapshot_id']) if row['_snapshot_id'] else None
    latest=students_repository.selected_prediction(db,row['_prediction_id']) if row['_prediction_id'] else None
    source=students_repository.selected_prediction(db,row['prediction_id'])
    history,truncated=repository.case_history(db,row['enrollment_id'],id)
    return s5.AlertDetail(alert=public_case(db,user,row),source_prediction=projection(s2.Prediction,source),
        latest_snapshot=s2.Snapshot.model_validate(snapshot) if snapshot else None,
        latest_prediction=projection(s2.Prediction,latest) if latest else None,
        interventions=[intervention_view(user,period,i) for i in repository.case_interventions(db,id)],
        history=[s2.TimelineEvent.model_validate(r) for r in history],history_truncated=truncated)


def lock_resource(db,user,id,settings,kind='alert'):
    require_writer(user)
    reference=repository.resource(db,user,id,kind)
    if reference is None:
        raise AppError(404,'ALERT_NOT_FOUND' if kind=='alert' else 'INTERVENTION_NOT_FOUND',
            'El caso no está disponible.' if kind=='alert' else 'La actividad no está disponible.')
    period,study,_=context_period(db,user,reference['period_id'],settings,reference['section_id'],write=True)
    repository.lock_enrollments(db,period.id,[reference['enrollment_id']])
    # Recheck scope after waiting for the enrollment lock (assignment may change).
    if repository.resource(db,user,id,kind) is None:
        raise AppError(404,'ALERT_NOT_FOUND' if kind=='alert' else 'INTERVENTION_NOT_FOUND','El recurso no está disponible.')
    return period,study,reference


def version_check(record,expected):
    if record.version!=expected:
        raise AppError(409,'VERSION_CONFLICT','El recurso cambió. Revisa su versión actual antes de reenviar tu borrador.')


def patch_alert(db,user,id,payload,settings,request_id):
    try:
        period,_,_=lock_resource(db,user,id,settings)
        record=repository.locked_alert(db,id)
        version_check(record,payload.expected_version)
        if record.status not in ACTIVE:
            raise AppError(409,'INVALID_TRANSITION','El caso está cerrado y su estado es definitivo.')
        allowed={'OPEN':('OPEN','IN_REVIEW','RESOLVED','DISMISSED'),
            'IN_REVIEW':('IN_REVIEW','RESOLVED','DISMISSED')}
        if payload.status not in allowed[record.status]:
            raise AppError(409,'INVALID_TRANSITION','La transición de estado no está permitida.')
        if record.status!=payload.status:
            previous={'status':record.status,'resolution_reason':record.resolution_reason,'version':record.version}
            record.status=payload.status;record.version+=1;record.updated_at=datetime.now(UTC)
            if record.status not in ACTIVE:
                record.resolution_reason=payload.resolution_reason.strip();record.closed_at=record.updated_at
            event(db,user,record,'ALERT','ALERT_STATUS_CHANGED',request_id,previous=previous,
                status=record.status,resolution_reason=record.resolution_reason,version=record.version)
            db.flush()
        result=detail(db,user,id,settings)
        db.commit();return result
    except IntegrityError as exc:
        db.rollback();raise domain_integrity(exc) from None
    except Exception:
        db.rollback();raise


def creation_digest(payload):
    # Includes original expected_alert_version and every original contractual value.
    encoded=json.dumps(payload.model_dump(mode='json'),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def create_intervention(db,user,payload,settings,request_id):
    digest=creation_digest(payload)
    try:
        period,_,_=lock_resource(db,user,payload.alert_id,settings)
        alert=repository.locked_alert(db,payload.alert_id)
        existing=repository.intervention_by_key(db,user.id,payload.creation_key)
        if existing:
            if repository.resource(db,user,existing.id,'intervention') is None:
                raise AppError(404,'INTERVENTION_NOT_FOUND','La actividad no está disponible.')
            if existing.creation_payload_sha256!=digest:
                raise AppError(409,'CREATION_KEY_CONFLICT','La clave de creación ya corresponde a otro contenido. Revisa la actividad antes de crear otra intención.')
            result=s5.InterventionCreateResult(intervention=intervention_view(user,period,existing),reused_result=True)
            db.commit();return result
        version_check(alert,payload.expected_alert_version)
        if alert.status not in ACTIVE:
            raise AppError(409,'ALERT_CLOSED','No puedes planificar actividades nuevas en un caso cerrado.')
        record=InterventionRecord(id=uuid4(),enrollment_id=alert.enrollment_id,alert_id=alert.id,
            data_origin='SYNTHETIC',created_by=user.id,kind=payload.kind,objective=payload.objective,
            scheduled_at=payload.scheduled_at.astimezone(UTC),notes=payload.notes,status='PLANNED',
            performed_at=None,version=1,creation_key=payload.creation_key,creation_payload_sha256=digest)
        db.add(record);db.flush()
        event(db,user,record,'INTERVENTION','INTERVENTION_CREATED',request_id,alert_id=str(alert.id),
            kind=record.kind,objective=record.objective,scheduled_at=record.scheduled_at.isoformat(),
            notes=record.notes,status=record.status,version=record.version)
        db.flush()
        result=s5.InterventionCreateResult(intervention=intervention_view(user,period,record),reused_result=False)
        db.commit();return result
    except IntegrityError as exc:
        db.rollback()
        # A unique-key winner on another enrollment can finish while we wait.
        existing=repository.intervention_by_key(db,user.id,payload.creation_key)
        if existing and repository.resource(db,user,existing.id,'intervention'):
            if existing.creation_payload_sha256!=digest:
                raise AppError(409,'CREATION_KEY_CONFLICT','La clave de creación ya corresponde a otro contenido.') from None
            reference=repository.resource(db,user,existing.id,'intervention')
            period,_,_=context_period(db,user,reference['period_id'],settings,reference['section_id'],write=True)
            result=s5.InterventionCreateResult(intervention=intervention_view(user,period,existing),reused_result=True)
            db.commit();return result
        raise domain_integrity(exc) from None
    except Exception:
        db.rollback();raise


def patch_intervention(db,user,id,payload,settings,request_id):
    try:
        period,_,reference=lock_resource(db,user,id,settings,'intervention')
        # Case first, activity second: same order as planning and sync.
        unlocked=db.get(InterventionRecord,id)
        if unlocked.alert_id:
            repository.locked_alert(db,unlocked.alert_id)
        record=repository.locked_intervention(db,id)
        version_check(record,payload.expected_version)
        if record.status!='PLANNED':
            raise AppError(409,'INVALID_TRANSITION','La actividad está realizada o cancelada y su estado es definitivo.')
        changes=payload.model_dump(exclude_unset=True,exclude={'expected_version'})
        if any(changes.get(k) is None and k in changes for k in ('kind','objective','scheduled_at','status')):
            raise AppError(422,'VALIDATION_ERROR','Tipo, objetivo, fecha y estado no pueden ser null.')
        target=changes.get('status',record.status)
        if target=='DONE':
            performed=changes.get('performed_at')
            if performed is None:
                raise AppError(422,'VALIDATION_ERROR','Indica la fecha efectiva de la actividad realizada.')
            if performed>datetime.now(UTC):
                raise AppError(422,'PERFORMED_AT_IN_FUTURE','La fecha efectiva no puede estar en el futuro del reloj del servidor.')
        else:
            changes['performed_at']=None
        for field in ('scheduled_at','performed_at'):
            if changes.get(field) is not None:
                changes[field]=changes[field].astimezone(UTC)
        effective={key:value for key,value in changes.items() if getattr(record,key)!=value}
        if effective:
            previous={key:getattr(record,key) for key in effective}
            previous={key:value.isoformat() if isinstance(value,datetime) else value for key,value in previous.items()}
            for key,value in effective.items():
                setattr(record,key,value)
            record.version+=1;record.updated_at=datetime.now(UTC)
            event(db,user,record,'INTERVENTION','INTERVENTION_UPDATED',request_id,previous=previous,
                status=record.status,version=record.version,changes={key:value.isoformat() if isinstance(value,datetime) else value for key,value in effective.items()})
            db.flush()
        result=intervention_view(user,period,record)
        db.commit();return result
    except IntegrityError as exc:
        db.rollback();raise domain_integrity(exc) from None
    except Exception:
        db.rollback();raise
