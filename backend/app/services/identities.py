"""Carga de identidades (código → nombre) a la ficha del alumno REAL. Solo ADMIN; todo o nada; auditoría sin nombres.

Los nombres solo llegan a `students.full_name`. El evento de auditoría guarda conteos y un identificador derivado de los CÓDIGOS
(nunca de los nombres); no se escribe ningún nombre en auditoría ni en registros.
"""
from hashlib import sha256
import unicodedata
from uuid import NAMESPACE_URL, uuid4, uuid5
from sqlalchemy import select
from app.core.errors import AppError
from app.models.s1 import AuditEvent
from app.models.s2 import StudentRecord

MAX_ROWS = 2000


def normalize(value):
    return ' '.join(unicodedata.normalize('NFC', value).split())


def load_identities(db, actor, rows, request_id=None):
    """rows: lista de (línea, código, nombre). Devuelve conteos. Los errores solo llevan líneas y códigos de causa."""
    if actor.role != 'ADMIN' or not actor.is_active:
        raise AppError(403, 'FORBIDDEN', 'Solo un administrador activo carga identidades.')
    if not rows or len(rows) > MAX_ROWS:
        raise AppError(422, 'IDENTITIES_ROWS_INVALID', 'El archivo de identidades está vacío o excede el máximo de filas.')
    problems, seen, prepared = [], set(), []
    for line, code, name in rows:
        code = ' '.join(str(code).split()).upper()
        name = normalize(str(name))
        if not name or len(name) > 160 or not 3 <= len(code) <= 40:
            problems.append({'row': line, 'code': 'IDENTITY_ROW_INVALID'})
        elif code in seen:
            problems.append({'row': line, 'code': 'CODE_DUPLICATED'})
        else:
            seen.add(code)
            prepared.append((line, code, name))
    students = {s.anon_code: s for s in db.scalars(select(StudentRecord).where(StudentRecord.anon_code.in_(seen), StudentRecord.data_origin == 'REAL')
                                                   .with_for_update())}
    for line, code, _ in prepared:
        if code not in students:
            problems.append({'row': line, 'code': 'CODE_UNKNOWN'})
    if problems:
        db.rollback()
        raise AppError(422, 'IDENTITIES_REJECTED', 'Hay filas rechazadas; no se cargó ninguna identidad.', details=problems[:50])
    updated = 0
    try:
        for _, code, name in prepared:
            student = students[code]
            if student.full_name != name:
                student.full_name = name
                student.version += 1
                updated += 1
        db.flush()
        digest = sha256('\n'.join(sorted(seen)).encode()).hexdigest()
        db.add(AuditEvent(actor_id=actor.id, entity_type='STUDENT_IDENTITIES', entity_id=uuid5(NAMESPACE_URL, 'identities:' + digest),
                          action='STUDENT_IDENTITIES_LOADED', request_id=request_id or uuid4(),
                          payload={'data_origin': 'REAL', 'rows': len(prepared), 'updated': updated, 'unchanged': len(prepared) - updated}))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'rows': len(prepared), 'updated': updated, 'unchanged': len(prepared) - updated}
