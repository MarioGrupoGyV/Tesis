"""ADR 014: copia de demostración del SVM REAL activo para el periodo DEMO-VIVO de la instalación hermana.

Excepción estrecha, solo con `DEMO_REAL_MODEL_COPY=true` (la instalación principal la deja apagada). La copia es un segundo registro
(`model_versions`, origen SYNTHETIC porque el periodo es de demostración) que apunta al **mismo artefacto** del SVM REAL activo: mismos
bytes, misma huella y su procedencia real intacta (no se reentrena, no se copia ni se reescribe ningún archivo ni registro de
entrenamiento). Solo evalúa el periodo cuyo código es DEMO-VIVO; hay una por periodo; deja auditoría al registrarse y al evaluar.
Apagado el interruptor, la copia nunca se reconoce y todas las comprobaciones se comportan como antes.
"""
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.core.errors import AppError
from app.models.ml import ModelVersion
from app.models.s1 import AcademicPeriod, AuditEvent
from app.models.synthetic import SyntheticStudyRecord

DEMO_PERIOD_CODE = 'DEMO-VIVO'
COPY_KIND = 'DEMO_COPY_OF_ACTIVE_REAL_MODEL'
COPY_NAME = 'SVM del estudio real (copia de demostración)'
DISPLAY_LABEL = 'SVM del estudio real'
NOTE = ('Mismo artefacto, byte a byte, que el modelo REAL activo; usado solo para la demostración en vivo del periodo DEMO-VIVO. '
        'El origen SYNTHETIC del registro se debe a que el periodo es de demostración; la procedencia del artefacto sigue siendo REAL (ADR 014).')


def enabled(settings) -> bool:
    return bool(getattr(settings, 'demo_real_model_copy', False))


def is_copy(model) -> bool:
    return (getattr(model, 'manifest', None) or {}).get('demo_copy', {}).get('kind') == COPY_KIND


def audit(db, actor_id, model_id, action, request_id, **payload):
    db.add(AuditEvent(actor_id=actor_id, entity_type='MODEL', entity_id=model_id, action=action, request_id=request_id,
                      recorded_at=datetime.now(UTC), payload={'data_origin': 'SYNTHETIC', 'model_id': str(model_id), **payload}))


def active_real(db, settings):
    """El SVM REAL activo con TODAS sus verificaciones normales (protocolo, estudio institucional, artefacto firmado)."""
    from app.services.ml import load_active_model
    real = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True), ModelVersion.data_origin == 'REAL',
                                                ModelVersion.status == 'APPROVED'))
    if real is None or real.study_id is None:
        raise AppError(409, 'DEMO_COPY_SOURCE_UNAVAILABLE', 'No hay un modelo REAL activo verificado que copiar.')
    study = db.get(SyntheticStudyRecord, real.study_id)
    period = db.get(AcademicPeriod, study.period_id) if study else None
    if period is None or period.data_origin != 'REAL':
        raise AppError(409, 'DEMO_COPY_SOURCE_UNAVAILABLE', 'No hay un modelo REAL activo verificado que copiar.')
    _, model, bundle = load_active_model(db, period, settings, datetime.now(UTC))
    if model.id != real.id or bundle.manifest['artifact_sha256'] != real.artifact_sha256:
        raise AppError(409, 'DEMO_COPY_SOURCE_UNAVAILABLE', 'No hay un modelo REAL activo verificado que copiar.')
    return real, bundle


def demo_period_of(db, study):
    period = db.get(AcademicPeriod, study.period_id)
    if period is None or period.data_origin != 'SYNTHETIC' or period.code != DEMO_PERIOD_CODE or study.data_origin != 'SYNTHETIC':
        raise AppError(422, 'DEMO_COPY_PERIOD_INVALID', 'La copia de demostración solo se usa en el periodo DEMO-VIVO.')
    return period


def verified_copy(db, settings, study, model):
    """Comprueba la copia y devuelve el artefacto REAL (cargado y verificado de la forma normal). Cualquier fallo: 409."""
    if not enabled(settings) or not is_copy(model):
        raise AppError(409, 'MODEL_INCOMPATIBLE', 'El modelo no cumple la procedencia y compatibilidad del estudio.')
    demo_period_of(db, study)
    copy = model.manifest['demo_copy']
    real, bundle = active_real(db, settings)
    if (model.study_id != study.id or model.data_origin != 'SYNTHETIC' or model.status != 'APPROVED'
            or str(real.id) != copy.get('source_model_id') or model.artifact_key != real.artifact_key
            or model.artifact_sha256 != real.artifact_sha256 or copy.get('artifact_sha256') != real.artifact_sha256
            or model.dataset_hash != real.dataset_hash or model.algorithm != real.algorithm
            or model.manifest.get('study_id') != str(study.id)):
        raise AppError(409, 'MODEL_INCOMPATIBLE', 'La copia de demostración ya no coincide con el modelo REAL activo.')
    return bundle


def register(db, user, settings, period_id, expected_sha256, request_id):
    """Registra y activa la copia en DEMO-VIVO (desactiva y retira el modelo sintético de ese periodo). Una sola por periodo."""
    from app.services.processing_policy import require_study, study_for_period
    from app.services.synthetic_study import require_admin, validate_registered
    require_admin(user)
    if not enabled(settings):
        raise AppError(409, 'DEMO_COPY_DISABLED', 'La copia de demostración está desactivada en esta instalación.')
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id == period_id).with_for_update(read=True))
    if period is None:
        raise AppError(404, 'PERIOD_NOT_FOUND', 'El periodo no está disponible.')
    if period.data_origin != 'SYNTHETIC' or period.code != DEMO_PERIOD_CODE:
        raise AppError(422, 'DEMO_COPY_PERIOD_INVALID', 'La copia de demostración solo se usa en el periodo DEMO-VIVO.')
    study, _ = study_for_period(db, period)
    require_study(study, period)
    validate_registered(db, settings, study)
    if db.scalar(select(ModelVersion.id).where(ModelVersion.study_id == study.id, ModelVersion.name == COPY_NAME)) is not None:
        raise AppError(409, 'DEMO_COPY_EXISTS', 'El periodo DEMO-VIVO ya tiene su copia de demostración.')
    real, bundle = active_real(db, settings)
    if expected_sha256 != real.artifact_sha256 or bundle.manifest['artifact_sha256'] != expected_sha256:
        raise AppError(409, 'DEMO_COPY_HASH_MISMATCH', 'La huella indicada no es la del modelo REAL activo.')
    copy = {'kind': COPY_KIND, 'source_model_id': str(real.id), 'source_artifact_key': real.artifact_key,
            'artifact_sha256': real.artifact_sha256, 'dataset_hash': real.dataset_hash, 'source_data_origin': 'REAL',
            'source_scope': bundle.manifest['scope'], 'source_approval_kind': real.manifest.get('approval_kind'),
            'display_label': DISPLAY_LABEL, 'note': NOTE}
    record = ModelVersion(id=uuid4(), study_id=study.id, name=COPY_NAME, version=study.id.hex, data_origin='SYNTHETIC',
        algorithm=real.algorithm, dataset_hash=real.dataset_hash, artifact_sha256=real.artifact_sha256, artifact_key=real.artifact_key,
        feature_schema_version=real.feature_schema_version, reference_criterion_version=real.reference_criterion_version,
        status='APPROVED', is_active=False, parameters=real.parameters, metrics=real.metrics,
        manifest={'scope': 'SYNTHETIC_STUDY', 'data_origin': 'SYNTHETIC', 'study_id': str(study.id), 'algorithm': real.algorithm,
                  'approval_kind': 'TECHNICAL_SIMULATION', 'horizon_days': bundle.manifest['horizon_days'], 'demo_copy': copy}, created_by=user.id)
    try:
        from app.repositories.imports import advisory_lock
        advisory_lock(db, 'active-model:SYNTHETIC')
        retired = []
        for current in db.scalars(select(ModelVersion).where(ModelVersion.data_origin == 'SYNTHETIC', ModelVersion.study_id == study.id)
                                  .with_for_update()):
            current.is_active = False
            current.status = 'RETIRED'                       # el modelo sintético del periodo no vuelve a evaluar ni se lista
            retired.append(str(current.id))
        for current in db.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True), ModelVersion.data_origin == 'SYNTHETIC')
                                  .with_for_update()):
            current.is_active = False
        db.flush()
        db.add(record)
        db.flush()
        verified_copy(db, settings, study, record)
        record.is_active = True
        db.flush()
        audit(db, user.id, record.id, 'DEMO_REAL_MODEL_COPY_REGISTERED', request_id, period_id=str(period.id), study_id=str(study.id),
              source_model_id=str(real.id), artifact_sha256=real.artifact_sha256, retired_synthetic_models=retired)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return record


def session_of(study):
    return object_session(study)
