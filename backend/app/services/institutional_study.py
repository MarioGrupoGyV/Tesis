"""Estudio institucional (REAL, local): registro del CSV canónico, dataset desde `risk_references`, comparación y modelos.

Reutiliza la tabla `synthetic_studies` (kind='INSTITUTIONAL_STUDY'), el almacenamiento privado y los servicios de registro/activación.
Nada de esto funciona sin un protocolo REAL confirmado que cubra el periodo (`require_real_protocol`). Solo códigos y números.
"""
import base64
from datetime import UTC, date, datetime, time
import hashlib
import json
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from app.core.errors import AppError
from app.core.study_storage import StudyStorage
from app.ml.features import CLASSES, MLDiagnostic, Dataset, FeatureConfig, Label, Observation, Scale
from app.models.protocol import ProcessingProtocolRecord
from app.models.s1 import AcademicPeriod, AuditEvent
from app.models.synthetic import SyntheticStudyRecord
from app.services import risk_reference_store
from app.services.processing_protocol import params_of, require_real_protocol
from app.services.risk_reference import RULE_VERSION

LIMA = ZoneInfo('America/Lima')
KIND = 'INSTITUTIONAL_STUDY'
GENERATOR = 'institutional-loader-v1'
SCOPE = 'INSTITUTIONAL_STUDY'
APPROVAL = 'LOCAL_EXPLORATORY'
# Decisión 4 (ADR 012): la participación no existe al corte; solo se usa en RIESGO_V1 con insumos de cierre.
FEATURES = ['average_grade', 'attendance_pct', 'activities_pct', 'behavior_incidents']
CRITERION = 'RIESGO_V1: cinco componentes de 0 a 2 puntos con insumos de cierre (Bajo 0–1, Medio 2–4, Alto ≥ 5)'


def require_admin(user):
    if user.role != 'ADMIN' or not user.is_active:
        raise AppError(403, 'FORBIDDEN', 'Se requiere un administrador activo autenticado.')


def horizon_days(params: dict) -> int:
    """Días entre la disponibilidad del último dato al corte y el cierre; debe ser el mismo en todos los bimestres."""
    values = {(date.fromisoformat(item['close_date']) - datetime.fromisoformat(item['cutoff_available_at']).astimezone(LIMA).date()).days
              for item in params['bimesters']}
    if len(values) != 1 or min(values) < 1:
        raise AppError(422, 'PROTOCOL_HORIZON_NOT_CONSTANT', 'Todos los bimestres deben tener el mismo horizonte entre el corte y el cierre.')
    return values.pop()


def feature_config(params: dict) -> FeatureConfig:
    grade = (float(params['grade_scale_min']), float(params['grade_scale_max']))
    scales = {'average_grade': Scale(minimum=grade[0], maximum=grade[1], decimals=2, unit='nota'),
              'attendance_pct': Scale(minimum=0, maximum=100, decimals=2, unit='%'),
              'activities_pct': Scale(minimum=0, maximum=100, decimals=2, unit='%'),
              'behavior_incidents': Scale(minimum=0, maximum=100, decimals=0, unit='conteo')}
    rules = params['eligibility_rules']
    if not set(rules['required_features']) <= set(FEATURES):
        raise AppError(422, 'PROTOCOL_REQUIRED_FEATURES_INVALID', 'Las variables requeridas deben estar entre las del corte (sin participación).')
    return FeatureConfig(criterion_version=RULE_VERSION, criterion_definition=CRITERION, horizon_days=horizon_days(params), scales=scales,
        participation_values=list(range(params['participation_min'], params['participation_max'] + 1)), base_features=list(FEATURES),
        inference_max_missing_fraction=rules['inference_max_missing_fraction'], required_features=list(rules['required_features']))


def csv_scales(params: dict) -> dict:
    return {'participation': (params['participation_min'], params['participation_max']),
            'grade': (float(params['grade_scale_min']), float(params['grade_scale_max']))}


def event(db, user, study, action, request_id, **payload):
    db.add(AuditEvent(actor_id=user.id, entity_type='INSTITUTIONAL_STUDY', entity_id=study.id, action=action,
                      request_id=request_id, payload={'data_origin': 'REAL', 'study_id': str(study.id), **payload}))


def study_id_for(protocol_id, csv_sha256):
    return uuid5(NAMESPACE_URL, f'{GENERATOR}:{protocol_id}:{csv_sha256}')


def register_study(db, user, settings, protocol_id, content: bytes, request_id):
    """Registra el CSV canónico de cortes de un periodo REAL con protocolo confirmado. Idempotente por contenido."""
    require_admin(user)
    from app.services.csv_validation import parse_csv
    protocol = db.scalar(select(ProcessingProtocolRecord).where(ProcessingProtocolRecord.id == protocol_id).with_for_update(read=True))
    if protocol is None:
        raise AppError(404, 'PROTOCOL_NOT_FOUND', 'El protocolo no está disponible.')
    period = db.scalar(select(AcademicPeriod).where(AcademicPeriod.id == protocol.period_id).with_for_update(read=True))
    require_real_protocol(db, period)
    if period.is_locked:
        raise AppError(409, 'PERIOD_LOCKED', 'El periodo está bloqueado.')
    params = params_of(protocol)
    config = feature_config(params)
    parsed = parse_csv(content, period, csv_scales(params))
    if parsed.errors or not parsed.rows:
        raise AppError(422, 'INSTITUTIONAL_CSV_INVALID', 'El CSV canónico tiene filas inválidas o está vacío. No se registró.',
                       details=[{'row': item['row'], 'field': item['column'], 'message': item['code']} for item in parsed.errors[:50]])
    horizons = {(row['target_date'] - row['cutoff_at'].astimezone(LIMA).date()).days for row in parsed.rows}
    if horizons != {config.horizon_days}:
        raise AppError(422, 'INSTITUTIONAL_HORIZON_MISMATCH', 'El horizonte de cada corte debe coincidir con el del protocolo.')
    digest = hashlib.sha256(content).hexdigest()
    identifier = study_id_for(protocol.id, digest)
    existing = db.get(SyntheticStudyRecord, identifier)
    if existing is not None:
        validate_institutional(db, settings, existing)
        return existing, True
    other = db.scalar(select(SyntheticStudyRecord.id).where(SyntheticStudyRecord.period_id == period.id))
    if other is not None:
        raise AppError(409, 'STUDY_EXISTS', 'El periodo ya tiene un estudio institucional con otro archivo.')
    config_json = {'protocol_id': str(protocol.id), 'protocol': params, 'feature_schema': config.model_dump(mode='json')}
    manifest_json = {'kind': KIND, 'generator_version': GENERATOR, 'csv_sha256': digest, 'rows': len(parsed.rows),
                     'students': len({row['student_code'] for row in parsed.rows}), 'horizon_days': config.horizon_days,
                     'limits': ['Datos reales locales; análisis exploratorio.', 'No demuestra eficacia escolar ni valida la tesis.']}
    payload = {'study_id': str(identifier), 'config': config_json, 'manifest': manifest_json,
               'csv_base64': base64.b64encode(content).decode()}
    key = identifier.hex + '.json'
    payload_sha = StudyStorage(settings.ml_storage_dir).write(key, payload)
    study = SyntheticStudyRecord(id=identifier, period_id=period.id, data_origin='REAL', generator_version=GENERATOR, seed=0,
        config=config_json, manifest=manifest_json, csv_sha256=digest, storage_key=key, payload_sha256=payload_sha,
        created_by=user.id, kind=KIND, protocol_id=protocol.id, bindings=[], comparison=None)
    try:
        db.add(study)
        db.flush()
        event(db, user, study, 'INSTITUTIONAL_STUDY_REGISTERED', request_id, protocol_id=str(protocol.id), rows=len(parsed.rows))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, 'STUDY_CONFLICT', 'No se pudo registrar el estudio institucional.') from None
    return study, False


def validate_institutional(db, settings, study):
    """Procedencia privada íntegra y protocolo vigente igual al congelado en el estudio."""
    period = db.get(AcademicPeriod, study.period_id)
    protocol = require_real_protocol(db, period)
    if (study.kind != KIND or study.data_origin != 'REAL' or study.generator_version != GENERATOR or study.protocol_id != protocol.id
            or params_of(protocol) != study.config.get('protocol')):
        raise AppError(409, 'STUDY_INTEGRITY_ERROR', 'Origen, contexto o protocolo del estudio incompatible.')
    payload = StudyStorage(settings.ml_storage_dir).read(study.storage_key, study.payload_sha256)
    content = base64.b64decode(payload['csv_base64'], validate=True)
    if (hashlib.sha256(content).hexdigest() != study.csv_sha256 or payload['config'] != study.config
            or payload['manifest'] != study.manifest or str(payload['study_id']) != str(study.id)):
        raise AppError(409, 'STUDY_INTEGRITY_ERROR', 'Procedencia del estudio incompatible.')
    return protocol, payload, content


def verified_csv(db, settings, period, content):
    from app.services.processing_policy import study_for_period
    study, _ = study_for_period(db, period)
    if study is None or hashlib.sha256(content).hexdigest() != study.csv_sha256:
        raise AppError(422, 'UNREGISTERED_INSTITUTIONAL_FILE', 'Usa el CSV canónico exacto registrado para este periodo. No se guardó el archivo.')
    _, _, registered = validate_institutional(db, settings, study)
    if registered != content:
        raise AppError(409, 'STUDY_INTEGRITY_ERROR', 'El archivo no coincide con su procedencia privada.')
    return study


def bind_batch(db, study, batch):
    rows = db.execute(text('''SELECT sn.id,s.anon_code,sn.cutoff_at,sn.source_row_number,sn.row_sha256,sn.revision
        FROM risk_school.academic_snapshots sn JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
        JOIN risk_school.students s ON s.id=e.student_id WHERE sn.import_batch_id=:b ORDER BY sn.source_row_number'''),
        {'b': batch.id}).all()
    study.bindings = [{'snapshot_id': str(r[0]), 'student_code': r[1], 'cutoff_at': r[2].isoformat(), 'source_row_number': r[3],
                       'row_sha256': r[4], 'revision': r[5]} for r in rows]
    db.flush()


def build_dataset(db, study, protocol):
    """Dataset REAL: características del corte (snapshots importados) y etiquetas de `risk_references`; nunca al revés."""
    config = feature_config(params_of(protocol))
    bound = [item['snapshot_id'] for item in study.bindings]
    if not bound:
        raise AppError(409, 'INSTITUTIONAL_IMPORT_REQUIRED', 'Importa primero el CSV canónico registrado.')
    rows = db.execute(text('''SELECT DISTINCT ON (sn.enrollment_id,sn.cutoff_at) sn.*,e.student_id,s.is_active,s.eligible_for_processing
        FROM risk_school.academic_snapshots sn JOIN risk_school.enrollments e ON e.id=sn.enrollment_id
        JOIN risk_school.students s ON s.id=e.student_id WHERE sn.period_id=:period AND sn.import_batch_id IS NOT NULL
        ORDER BY sn.enrollment_id,sn.cutoff_at,sn.revision DESC'''), {'period': study.period_id}).mappings().all()
    references = risk_reference_store.latest_by_snapshot(db, study.period_id)
    exclusions, observations, labels = {}, [], []

    def drop(reason):
        exclusions[reason] = exclusions.get(reason, 0) + 1
    for row in rows:
        reference = references.get(row['id'])
        values = {name: float(row[name]) if row[name] is not None else None for name in config.features}
        if not (row['is_active'] and row['eligible_for_processing']):
            drop('NOT_ELIGIBLE')
        elif reference is None:
            drop('NO_REFERENCE')
        elif (any(values[name] is None for name in config.required_features) or
              sum(v is None for v in values.values()) / len(values) > config.inference_max_missing_fraction):
            drop('INFERENCE_ABSTENTION')
        else:
            observations.append(Observation(student_key=str(row['student_id']), snapshot_id=row['id'], enrollment_id=row['enrollment_id'],
                period_id=row['period_id'], data_origin='REAL', schema_version='academic-v1', revision=row['revision'],
                supersedes_id=row['supersedes_id'], window_start=row['window_start'], available_at=row['available_at'],
                cutoff_at=row['cutoff_at'], target_date=row['target_date'], created_at=row['created_at'], eligible=True, values=values,
                feature_available_at={name: row['available_at'] for name in config.features}, input_provenance='snapshot:' + str(row['id'])))
            observed = datetime.combine(reference.closing_date, time(0, 0), tzinfo=LIMA)
            labels.append(Label(snapshot_id=row['id'], risk=reference.risk_level, criterion_version=RULE_VERSION,
                outcome_definition=config.criterion_definition, provenance='risk_reference:' + str(reference.id),
                observed_at=observed, available_at=reference.closing_available_at))
    if not observations:
        raise AppError(422, 'INSUFFICIENT_DATA_FOR_STUDY', 'No hay cortes elegibles con riesgo de referencia para comparar modelos.',
                       details=[{'row': 0, 'field': key, 'message': str(value)} for key, value in sorted(exclusions.items())])
    as_of = max([label.available_at for label in labels] + [row.created_at for row in observations])
    dataset = Dataset(schema_version='ml-dataset-v1', scope='INSTITUTIONAL', provenance=f'{GENERATOR}:{study.csv_sha256}',
                      evaluation_as_of=as_of, config=config, observations=observations, labels=labels)
    return dataset, exclusions


def selected_artifact(settings, study):
    from app.ml.artifacts import ArtifactStore
    if not study.comparison or not study.bindings:
        raise AppError(409, 'INSTITUTIONAL_COMPARISON_REQUIRED', 'Compara primero los modelos del estudio institucional.')
    algorithm = study.comparison['selected_algorithm']
    key = study.comparison['artifact_keys'][algorithm]
    manifest, _, _ = ArtifactStore(settings.ml_storage_dir).inspect(key)
    if (manifest['scope'] != SCOPE or manifest['data_origin'] != 'REAL' or str(manifest['study_id']) != str(study.id)
            or manifest['algorithm'] != algorithm or manifest['feature_schema'] != study.config['feature_schema']
            or manifest.get('generator_version') != GENERATOR
            or manifest['institutional_evaluation']['source_dataset_hash'] != study.comparison['report']['source_dataset_hash']
            or manifest['institutional_evaluation']['base_seed'] != study.comparison['report']['seed']):
        raise AppError(409, 'MODEL_INCOMPATIBLE', 'El artefacto no cumple la procedencia y compatibilidad del estudio.')
    return manifest, key


def compatible_model(settings, study, model):
    manifest, key = selected_artifact(settings, study)
    if (not study.comparison or not study.bindings or model.status != 'APPROVED' or model.data_origin != 'REAL'
            or model.algorithm != study.comparison['selected_algorithm'] or key != model.artifact_key
            or model.study_id != study.id or str(manifest['study_id']) != str(study.id)
            or manifest['algorithm'] != model.algorithm or manifest['dataset_hash'] != model.dataset_hash
            or manifest['artifact_sha256'] != model.artifact_sha256
            or manifest['feature_schema']['schema_version'] != model.feature_schema_version
            or manifest['reference_criterion_version'] != model.reference_criterion_version
            or model.manifest != {**manifest, 'approval_kind': APPROVAL}
            or model.parameters != manifest['parameters'] or model.metrics != manifest['metrics']):
        raise AppError(409, 'MODEL_INCOMPATIBLE', 'El modelo no cumple la procedencia y compatibilidad del estudio.')
    return manifest


def compare_registered(db, user, settings, study, request_id, repetitions=None, leave_one_student_out=False):
    """Compara RF/SVM/XGBoost/DUMMY con CV agrupada repetida (ver app.ml.institutional). Reutiliza si ya existe."""
    from app.ml.artifacts import ArtifactStore
    from app.ml.institutional import DEFAULT_REPETITIONS, compare_institutional
    protocol, _, _ = validate_institutional(db, settings, study)
    if not study.bindings:
        raise AppError(409, 'INSTITUTIONAL_IMPORT_REQUIRED', 'Importa primero el CSV canónico registrado.')
    if study.comparison:
        for key in study.comparison['artifact_keys'].values():
            ArtifactStore(settings.ml_storage_dir).inspect(key)
        return {**study.comparison['report'], 'reused': True}
    dataset, exclusions = build_dataset(db, study, protocol)
    try:
        result = compare_institutional(dataset, seed=0 if study.seed is None else int(study.seed), study_id=study.id,
                                       repetitions=repetitions or DEFAULT_REPETITIONS, leave_one_student_out=leave_one_student_out)
    except MLDiagnostic as error:
        raise AppError(422, 'INSTITUTIONAL_COMPARISON_FAILED', 'No se pudo comparar: ' + str(error) + '.') from None
    store = ArtifactStore(settings.ml_storage_dir)
    keys = {algorithm: store.save(bundle, result.training_dataset) for algorithm, bundle in result.bundles.items()}
    report = {**result.report, 'exclusions': exclusions}
    study.comparison = {'artifact_keys': keys, 'report': report, 'selected_algorithm': result.selected_algorithm}
    event(db, user, study, 'INSTITUTIONAL_MODELS_COMPARED', request_id, algorithms=list(keys),
          selected_algorithm=result.selected_algorithm, repetitions=report['repetitions'])
    db.commit()
    return {**report, 'reused': False}


def register_model(db, user, settings, study, algorithm, request_id):
    from app.models.ml import ModelVersion
    from uuid import uuid4
    validate_institutional(db, settings, study)
    if not study.comparison or not study.bindings:
        raise AppError(409, 'INSTITUTIONAL_COMPARISON_REQUIRED', 'Compara primero los modelos del estudio institucional.')
    algorithm = algorithm or study.comparison['selected_algorithm']
    if algorithm != study.comparison['selected_algorithm']:
        raise AppError(422, 'MODEL_NOT_SELECTED', 'Registra únicamente el algoritmo seleccionado por la regla del estudio.')
    manifest, key = selected_artifact(settings, study)
    record = db.scalar(select(ModelVersion).where(ModelVersion.study_id == study.id, ModelVersion.algorithm == algorithm))
    if record:
        compatible_model(settings, study, record)
        return record, True
    record = ModelVersion(id=uuid4(), study_id=study.id, name='Estudio institucional ' + algorithm, version=study.id.hex,
        data_origin='REAL', algorithm=algorithm, dataset_hash=manifest['dataset_hash'], artifact_sha256=manifest['artifact_sha256'],
        artifact_key=key, feature_schema_version=manifest['feature_schema']['schema_version'],
        reference_criterion_version=manifest['reference_criterion_version'], status='APPROVED', is_active=False,
        parameters=manifest['parameters'], metrics=manifest['metrics'], manifest={**manifest, 'approval_kind': APPROVAL}, created_by=user.id)
    compatible_model(settings, study, record)
    db.add(record)
    db.flush()
    event(db, user, study, 'INSTITUTIONAL_MODEL_REGISTERED', request_id, model_id=str(record.id), algorithm=algorithm, approval_kind=APPROVAL)
    db.commit()
    return record, False
