"""Vista previa versionada y confirmación atómica, con archivos privados inmutables."""
from datetime import UTC, datetime
import hashlib
import re
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.services.processing_policy import require_processing_protocol
from app.core.import_storage import ImportStorage
from app.models.s1 import AuditEvent
from app.models.s2 import EnrollmentRecord, ImportBatchRecord, SnapshotRecord, StudentRecord
from app.repositories import imports as repository
from app.schemas.s2 import ImportBatch, ImportCommit
from app.services.csv_validation import FEATURES, issue, parse_csv


def require_admin(user):
    if user.role != "ADMIN":
        raise AppError(403, "FORBIDDEN", "Solo el administrador puede consultar o confirmar importaciones.")


def institutional_period(period):
    if period is None:
        raise AppError(404, "PERIOD_NOT_FOUND", "El periodo solicitado no existe.")
    if period.data_origin not in ("REAL", "SYNTHETIC"):
        raise AppError(422, "ORIGIN_NOT_SUPPORTED", "El origen del recurso no corresponde al entorno institucional.")


def writable(period):
    if period.is_locked:
        raise AppError(409, "PERIOD_LOCKED", "El periodo está bloqueado y no admite importaciones.")


def stale():
    return AppError(409, "IMPORT_PREVIEW_STALE", "El estado cambió desde la vista previa. Vuelve a cargar el mismo archivo y revisa la nueva versión antes de confirmar.")


def observed_plan(db, period, parsed):
    sections, tutors, students, enrollments, snapshots = repository.observed_records(db, period, parsed.rows)
    errors = list(parsed.errors)
    observed = []
    for row in parsed.rows:
        source = row["source_row_number"]
        section = sections.get((row["grade"], row["section"]))
        student = students.get(row["student_code"])
        enrollment = enrollments.get(student.id) if student else None
        predecessor = snapshots.get((enrollment.id, row["cutoff_at"])) if enrollment else None
        if section is None:
            errors.append(issue(source, "section", "Usa un grado y sección existentes en el año escolar del periodo.", "SECTION_NOT_FOUND"))
        tutor = tutors.get(section.tutor_id) if section else None
        if section and section.tutor_id and (tutor is None or tutor.role != "TUTOR" or not tutor.is_active):
            errors.append(issue(source, "section", "Corrige la asignación: el responsable de sección debe ser un tutor activo.", "INVALID_TUTOR"))
        if student and student.data_origin != period.data_origin:
            raise AppError(422, "ORIGIN_NOT_SUPPORTED", "El código pertenece a un origen no habilitado. No se transforma el origen de registros existentes.",
                           details=[{"row": source, "field": "student_code", "message": "Conserva la trazabilidad del origen; no reutilices registros históricos."}])
        if student and not student.is_active:
            errors.append(issue(source, "student_code", "Usa un estudiante activo.", "STUDENT_INACTIVE"))
        if enrollment and section and enrollment.section_id != section.id:
            errors.append(issue(source, "section", "Conserva la sección de la matrícula existente; una importación no traslada estudiantes.", "ENROLLMENT_SECTION_CONFLICT"))
        observed.append({
            "source_row_number": source, "student_code": row["student_code"], "row_sha256": row["row_sha256"],
            "student_id": str(student.id) if student else None,
            "enrollment_id": str(enrollment.id) if enrollment else None,
            "section_id": str(section.id) if section else None,
            "section_tutor_id": str(section.tutor_id) if section and section.tutor_id else None,
            "student_active": student.is_active if student else None,
            "student_eligible": student.eligible_for_processing if student else None,
            "predecessor_id": str(predecessor.id) if predecessor else None,
            "predecessor_revision": predecessor.revision if predecessor else None,
            "create_snapshot": predecessor is None or predecessor.row_sha256 != row["row_sha256"],
            "period_start": period.start_date.isoformat(), "period_end": period.end_date.isoformat(),
            "school_year": period.school_year,
        })
    invalid = {e["row"] for e in errors if e["row"] >= 2}
    valid_plan = [r for r in observed if r["source_row_number"] not in invalid]
    counts = {
        "total_rows": parsed.total, "invalid_rows": len(invalid), "valid_rows": parsed.total - len(invalid),
        "planned_students": len({r["student_code"] for r in valid_plan if r["student_id"] is None}),
        "planned_enrollments": len({r["student_code"] for r in valid_plan if r["enrollment_id"] is None}),
        "planned_snapshots": sum(r["create_snapshot"] for r in valid_plan),
    }
    return observed, errors, counts


def audit(db, user, batch, request_id, action, **counts):
    db.add(AuditEvent(actor_id=user.id, entity_type="import_batch", entity_id=batch.id,
                      action=action, request_id=request_id,
                      payload={"data_origin": batch.data_origin, "preview_version": batch.preview_version, **counts}))


def precheck(db):
    from app.services.processing_policy import synthetic_studies
    if not synthetic_studies(db):
        require_processing_protocol()


def registered_source(db,settings,period,content):
    if period.data_origin=='REAL':
        require_processing_protocol()
        return None  # Solo pruebas históricas del motor sustituyen esta función bloqueante.
    from app.services.synthetic_study import verified_csv
    return verified_csv(db,settings,period,content)


def preview(db, user, settings, period_id, content, filename, request_id):
    require_admin(user)
    precheck(db)
    period = repository.locked_period(db, period_id)
    institutional_period(period)
    study = registered_source(db,settings,period,content)
    file_hash = hashlib.sha256(content).hexdigest()
    batch = repository.locked_batch(db, period_id, file_hash)
    if batch and batch.status == "COMMITTED":
        return ImportBatch.model_validate(batch), False
    writable(period)
    parsed = parse_csv(content, period)
    observed, errors, counts = observed_plan(db, period, parsed)
    storage = ImportStorage(settings.import_storage_dir)
    created = batch is None
    new_key = None
    try:
        if created:
            batch_id = uuid4()
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", (filename or "importacion.csv").replace("\\", "/").split("/")[-1])[:120]
            batch = ImportBatchRecord(id=batch_id, period_id=period.id, data_origin=period.data_origin, created_by=user.id,
                                      study_id=study.id if study else None,
                                      file_name=name or "importacion.csv", file_sha256=file_hash, storage_key=batch_id.hex + ".csv",
                                      schema_version="academic-v1", preview_version=1)
            storage.write(batch.storage_key, content)
            new_key = batch.storage_key
            db.add(batch)
        else:
            # No reemplazar evidencia almacenada al refrescar una vista previa.
            storage.read(batch.storage_key, batch.file_sha256)
            batch.preview_version += 1
        batch.status = "FAILED" if errors else "READY"
        batch.errors, batch.preview_state = errors, observed
        for key, value in counts.items():
            setattr(batch, key, value)
        db.flush()
        audit(db, user, batch, request_id, "IMPORT_PREVIEW_CREATED" if created else "IMPORT_PREVIEW_REFRESHED", **counts)
        result = ImportBatch.model_validate(batch)
        db.commit()
        return result, created
    except Exception:
        db.rollback()
        if new_key:
            storage.discard_uncommitted(new_key)
        raise


def get_batch(db, user, batch_id):
    require_admin(user)
    batch = db.get(ImportBatchRecord, batch_id)
    if batch is None:
        raise AppError(404, "IMPORT_NOT_FOUND", "El lote solicitado no existe.")
    if batch.data_origin not in ("REAL", "SYNTHETIC"):
        raise AppError(422, "ORIGIN_NOT_SUPPORTED", "El origen del recurso no corresponde al entorno institucional.")
    return batch


def committed_result(db, batch, reused):
    count = db.scalar(select(func.count()).select_from(SnapshotRecord).where(SnapshotRecord.import_batch_id == batch.id))
    return ImportCommit(batch_id=batch.id, created_snapshots=count, reused_result=reused)


def insert_snapshots(db, batch, rows, observed):
    from uuid import UUID
    by_code = {state['student_code']: state for state in observed}
    students = {code: StudentRecord(anon_code=code, data_origin=batch.data_origin,
                eligible_for_processing=batch.data_origin=='SYNTHETIC',consent_documented=False,assent_documented=False)
                for code, state in by_code.items() if state['student_id'] is None}
    db.add_all(list(students.values()))
    db.flush()
    student_ids = {code: UUID(state['student_id']) if state['student_id'] else students[code].id
                   for code, state in by_code.items()}
    enrollments = {code: EnrollmentRecord(student_id=student_ids[code], period_id=batch.period_id,
                    section_id=UUID(state['section_id']), data_origin=batch.data_origin)
                   for code, state in by_code.items() if state['enrollment_id'] is None}
    db.add_all(list(enrollments.values()))
    db.flush()
    enrollment_ids = {code: UUID(state['enrollment_id']) if state['enrollment_id'] else enrollments[code].id
                      for code, state in by_code.items()}
    snapshots = []
    for row, state in zip(rows, observed, strict=True):
        code = row["student_code"]
        if state["create_snapshot"]:
            record = SnapshotRecord(enrollment_id=enrollment_ids[code], period_id=batch.period_id, data_origin=batch.data_origin,
                import_batch_id=batch.id, revision=(state["predecessor_revision"] or 0) + 1,
                supersedes_id=UUID(state["predecessor_id"]) if state["predecessor_id"] else None,
                **{k: row[k] for k in (*FEATURES, "window_start", "cutoff_at", "available_at", "target_date",
                                      "missing_fraction", "source_row_number", "row_sha256")})
            snapshots.append(record)
    db.add_all(snapshots)
    db.flush()


def commit(db, user, settings, batch_id, expected_version, request_id):
    require_admin(user)
    precheck(db)
    initial = get_batch(db, user, batch_id)
    period = repository.locked_period(db, initial.period_id)
    institutional_period(period)
    if period.data_origin=='REAL':
        require_processing_protocol()
    batch = repository.locked_batch(db, period.id, initial.file_sha256)
    if batch.status == "COMMITTED":
        return committed_result(db, batch, True)
    writable(period)
    if batch.preview_version != expected_version:
        raise stale()
    if batch.status != "READY" or batch.invalid_rows or batch.errors:
        raise AppError(422, "IMPORT_INVALID", "Corrige todas las filas y revisa una nueva vista previa antes de confirmar.")
    content = ImportStorage(settings.import_storage_dir).read(batch.storage_key, batch.file_sha256)
    study = registered_source(db,settings,period,content)
    try:
        parsed = parse_csv(content, period)
        observed, errors, counts = observed_plan(db, period, parsed)
    except AppError as exc:
        if exc.code == "ORIGIN_NOT_SUPPORTED":
            raise
        raise stale() from None
    if errors or observed != batch.preview_state or any(getattr(batch, key) != value for key, value in counts.items()):
        raise stale()
    try:
        insert_snapshots(db, batch, parsed.rows, observed)
        if study:
            from app.services.synthetic_study import bind_imported
            bind_imported(db,study,batch,parsed.rows,settings)
        batch.status, batch.committed_at = "COMMITTED", datetime.now(UTC)
        audit(db, user, batch, request_id, "IMPORT_COMMITTED", **counts)
        db.flush()
        result = committed_result(db, batch, False)
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise stale() from None
        raise AppError(409, "INTEGRITY_CONFLICT", "No se pudo confirmar por un conflicto de integridad. El lote no dejó escrituras académicas parciales.") from None
    except Exception:
        db.rollback()
        raise
