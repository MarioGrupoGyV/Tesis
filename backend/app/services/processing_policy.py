"""La preparación sintética jamás habilita procesamiento institucional."""
from app.core.errors import AppError


def ml_readiness():
    return {'ready': False, 'code': 'INSTITUTIONAL_PROCESSING_NOT_READY',
            'missing': ['procedencia autorizada', 'escalas y criterio de referencia',
                        'etiquetas futuras verificables', 'calendario y protocolo',
                        'política de elegibilidad y faltantes', 'migración de activación'],
            'institutional_training': False, 'activation': False, 'institutional_inference': False}


def require_ml_protocol():
    raise AppError(422, 'INSTITUTIONAL_PROCESSING_NOT_READY',
        'Entrenamiento e inferencia institucional pendientes de protocolo, datos autorizados y activación. No se procesaron registros.')


def require_processing_protocol():
    # Sin interruptor de configuración: habilitar exige otra iteración revisada.
    raise AppError(422, 'INSTITUTIONAL_PROCESSING_NOT_READY',
        'La importación institucional está pendiente de autorización de procedencia, escala, periodo, ventanas temporales y reglas de calidad. No se guardó el archivo.')


def study_for_period(db, period):
    """Punto único para resolver el contexto de procesamiento de un periodo (ADR 012, Mapa de impacto).

    SYNTHETIC: estudio sintético registrado (puede ser None si no se preparó). REAL: exige un protocolo confirmado
    que cubra el periodo (si no, INSTITUTIONAL_PROCESSING_NOT_READY como siempre) y devuelve el estudio institucional.
    Devuelve (estudio | None, protocolo | None)."""
    from sqlalchemy import select
    from app.models.synthetic import SyntheticStudyRecord
    from app.services.processing_protocol import require_real_protocol
    if period.data_origin == 'REAL':
        protocol = require_real_protocol(db, period)
    elif period.data_origin == 'SYNTHETIC':
        protocol = None
    else:
        raise AppError(422, 'ORIGIN_NOT_SUPPORTED', 'Origen no admitido en este entorno.')
    study = db.scalar(select(SyntheticStudyRecord).where(SyntheticStudyRecord.period_id == period.id,
                                                          SyntheticStudyRecord.data_origin == period.data_origin))
    return study, protocol


def require_study(study, period):
    if study is None:
        if period.data_origin == 'REAL':
            raise AppError(422, 'INSTITUTIONAL_STUDY_NOT_PREPARED', 'El estudio institucional del periodo no está registrado.')
        raise AppError(422, 'SYNTHETIC_STUDY_NOT_PREPARED', 'El estudio sintético no está preparado.')
    return study


def synthetic_studies(db):
    from sqlalchemy import select
    from app.models.synthetic import SyntheticStudyRecord
    return db.scalars(select(SyntheticStudyRecord).order_by(SyntheticStudyRecord.id)).all()


def processing_status(db,user,settings):
    from sqlalchemy import select
    from app.models.ml import ModelVersion
    from app.models.s1 import AcademicPeriod
    from app.services.synthetic_study import validate_registered
    from app.schemas.processing import ProcessingStatus
    all_studies = synthetic_studies(db)
    studies = [s for s in all_studies if s.kind!='INSTITUTIONAL_STUDY']
    valid = []
    for study in studies:
        try:
            validate_registered(db,settings,study)
            valid.append(study)
        except (AppError,ValueError):
            continue
    prepared = bool(valid)
    writable=[s for s in valid if not db.get(AcademicPeriod,s.period_id).is_locked]
    committed = any(study.bindings for study in writable)
    from app.services.synthetic_study import selected_artifact
    compared=False
    for study in writable:
        if study.comparison and study.bindings:
            try:
                selected_artifact(settings,study)
                compared=True
            except (AppError,ValueError):
                continue
    # Modelo REAL activo y compatible con un estudio institucional vigente (protocolo confirmado): inferencia local exploratoria.
    institutional_ready=False
    from app.services.institutional_study import compatible_model as institutional_compatible, validate_institutional
    for study in all_studies:
        if study.kind!='INSTITUTIONAL_STUDY':
            continue
        try:
            validate_institutional(db,settings,study)
            active_real=db.scalar(select(ModelVersion).where(ModelVersion.study_id==study.id,ModelVersion.is_active.is_(True),
                ModelVersion.status=='APPROVED',ModelVersion.data_origin=='REAL'))
            if active_real is not None:
                institutional_compatible(settings,study,active_real)
                institutional_ready=True
        except (AppError,ValueError,OSError):
            continue
    models=db.scalars(select(ModelVersion).where(ModelVersion.status=='APPROVED',ModelVersion.data_origin=='SYNTHETIC',
        ModelVersion.study_id.in_([s.id for s in writable]))).all()
    compatible=[]
    from app.services.synthetic_study import compatible_model
    for model in models:
        try:
            study=next(s for s in writable if s.id==model.study_id)
            compatible_model(settings,study,model)
            compatible.append(model)
        except (AppError,ValueError):
            continue
    active=any(model.is_active for model in compatible)
    admin = user.role=='ADMIN'
    from app.repositories.s1 import sections_for_period
    readable = prepared and (user.role in ('ADMIN','DIRECTOR') or
        user.role=='TUTOR' and any(sections_for_period(db,db.get(AcademicPeriod,s.period_id),user.id) for s in valid))
    writable_readable = bool(writable) and (user.role=='ADMIN' or
        user.role=='TUTOR' and any(sections_for_period(db,db.get(AcademicPeriod,s.period_id),user.id) for s in writable))
    def op(role_ok,ready,reason):
        return {'available':bool(role_ok and ready),'reason':None if role_ok and ready else 'ROLE_RESTRICTED' if not role_ok else reason}
    from app.repositories.s1 import institutional_periods
    academic_readable = user.role in ('ADMIN','DIRECTOR') or user.role=='TUTOR' and bool(institutional_periods(db,user.id))
    return ProcessingStatus.model_validate({'scope':'SYNTHETIC_STUDY',
        'notice':'Registro académico local disponible según rol y origen. '+('Inferencia local exploratoria con protocolo REAL confirmado; no sustituye validación externa.' if institutional_ready else 'Inferencia institucional pendiente de protocolo.'),
        'institutional_ready':institutional_ready,'synthetic_ready':prepared,
        'operations':{'import':op(admin,bool(writable),'SYNTHETIC_STUDY_NOT_PREPARED_OR_LOCKED'),
          'compare':op(admin,committed,'SYNTHETIC_IMPORT_REQUIRED'),
          'register':op(admin,compared,'SYNTHETIC_COMPARISON_REQUIRED'),
          'activate':op(admin,bool(compatible),'SYNTHETIC_REGISTERED_MODEL_REQUIRED'),
          'predict':op(admin,active,'MODEL_NOT_AVAILABLE'),
          'read_students':op(user.role in ('ADMIN','TUTOR','DIRECTOR'),academic_readable,'ACADEMIC_CONTEXT_NOT_ACCESSIBLE'),
          'read_models':op(admin,True,None),
          'read_alerts':op(user.role in ('ADMIN','TUTOR','DIRECTOR'),readable,'SYNTHETIC_CONTEXT_NOT_ACCESSIBLE'),
          'write_followup':op(user.role in ('ADMIN','TUTOR'),writable_readable,'SYNTHETIC_CONTEXT_NOT_ACCESSIBLE_OR_LOCKED'),
          'sync_alerts':op(admin,active,'MODEL_NOT_AVAILABLE'),
          'read_reports':op(user.role in ('ADMIN','TUTOR','DIRECTOR'),readable,'SYNTHETIC_CONTEXT_NOT_ACCESSIBLE'),
          'export_reports':op(user.role in ('ADMIN','TUTOR','DIRECTOR'),readable,'SYNTHETIC_CONTEXT_NOT_ACCESSIBLE')}})
