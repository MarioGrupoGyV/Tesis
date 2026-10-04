"""Semilla explícita e idempotente; sin estudiantes, cortes ni entrenamiento.

Ejecutar: python -m app.seed_demo
DEMO_CREDENTIALS_FILE apunta a JSON ignorado por Git con admin/tutor/director,
cada uno con email y password. Nunca se imprime su contenido.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import Database
from app.core.security import password_hash, password_verify
from app.models.s1 import AcademicPeriod, AppUser, AuditEvent, GradeSection
from app.repositories.s1 import user_by_email

SEED_NAMESPACE = UUID("457a23b5-cb69-5f80-9a9b-1cd3e42eb104")


def seed_id(name: str) -> UUID:
    return uuid5(SEED_NAMESPACE, "risk-school-demo-v1:" + name)


class DemoCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=12, max_length=200)


class DemoCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    admin: DemoCredential
    tutor: DemoCredential
    director: DemoCredential


class SeedError(Exception):
    pass


def load_credentials(path: Path) -> DemoCredentials:
    if path.stat().st_size > 8192:
        raise SeedError("El archivo de credenciales excede el tamaño admitido.")
    credentials = DemoCredentials.model_validate_json(path.read_text(encoding="utf-8"))
    emails = [str(getattr(credentials, name).email).lower() for name in ("admin", "tutor", "director")]
    if len(set(emails)) != 3:
        raise SeedError("Las tres cuentas de demostración necesitan correos distintos.")
    return credentials


def seed_demo(db: Session, credentials: DemoCredentials) -> dict:
    """El llamador conserva el control de commit/rollback de toda la semilla."""
    # Bloqueo transaccional para impedir dos siembras simultáneas; no contiene datos sensibles.
    db.execute(text("SELECT pg_advisory_xact_lock(73421001)"))
    if db.scalar(select(AcademicPeriod.id).where(AcademicPeriod.data_origin != "DEMO").limit(1)):
        raise SeedError("La semilla requiere una base de demostración sin periodos REAL.")
    counts = {"data_origin": "DEMO", "users_created": 0, "periods_created": 0, "sections_created": 0}
    event_request_id = uuid4()

    def audit(entity_type: str, entity_id: UUID, role: str | None = None) -> None:
        payload = {"data_origin": "DEMO", "synthetic": True}
        if role is not None:
            payload["role"] = role
        db.add(AuditEvent(
            id=seed_id("audit:" + entity_type + ":" + str(entity_id)),
            actor_id=None,
            entity_type=entity_type,
            entity_id=entity_id,
            action="DEMO_SEEDED",
            request_id=event_request_id,
            payload=payload,
        ))

    for name, role, display_name in (
        ("admin", "ADMIN", "Administrador de demostración"),
        ("tutor", "TUTOR", "Tutor de demostración"),
        ("director", "DIRECTOR", "Directivo de demostración"),
    ):
        credential = getattr(credentials, name)
        expected_id = seed_id("user:" + name)
        user = db.get(AppUser, expected_id)
        if user is not None:
            if (
                user.role != role
                or user.email != str(credential.email).lower()
                or not user.is_active
                or not password_verify(credential.password.get_secret_value(), user.password_hash)
            ):
                raise SeedError("Una cuenta demo existente difiere de la semilla. No se sobrescribieron datos.")
            continue
        if user_by_email(db, str(credential.email).lower()) is not None:
            raise SeedError("Una cuenta existente colisiona con la semilla. No se sobrescribieron datos.")
        db.add(AppUser(
            id=expected_id,
            email=str(credential.email).lower(),
            display_name=display_name,
            password_hash=password_hash(credential.password.get_secret_value()),
            role=role,
            is_active=True,
        ))
        audit("app_user", expected_id, role)
        counts["users_created"] += 1
    db.flush()

    period_id = seed_id("period:2026")
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        existing = db.scalar(select(AcademicPeriod.id).where(AcademicPeriod.code == "DEMO-2026", AcademicPeriod.data_origin == "DEMO"))
        if existing:
            raise SeedError("El periodo existente colisiona con la semilla. No se sobrescribieron datos.")
        db.add(AcademicPeriod(
            id=period_id,
            code="DEMO-2026",
            school_year=2026,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 12, 31),
            data_origin="DEMO",
            is_locked=False,
        ))
        audit("academic_period", period_id)
        counts["periods_created"] += 1
    elif (period.data_origin, period.code, period.school_year, period.start_date, period.end_date) != (
        "DEMO", "DEMO-2026", 2026, date(2026, 3, 1), date(2026, 12, 31)
    ):
        raise SeedError("El periodo demo existente difiere de la semilla. No se sobrescribieron datos.")

    for grade, tutor_id in ((1, seed_id("user:tutor")), (2, None)):
        section_id = seed_id(f"section:2026:{grade}:A")
        section = db.get(GradeSection, section_id)
        if section is not None:
            if (section.grade, section.code, section.school_year, section.tutor_id) != (grade, "A", 2026, tutor_id):
                raise SeedError("Una sección demo existente difiere de la semilla. No se sobrescribieron datos.")
            continue
        if db.scalar(select(GradeSection.id).where(GradeSection.grade == grade, GradeSection.code == "A", GradeSection.school_year == 2026)):
            raise SeedError("Una sección existente colisiona con la semilla. No se sobrescribieron datos.")
        db.add(GradeSection(id=section_id, code="A", grade=grade, school_year=2026, tutor_id=tutor_id))
        audit("grade_section", section_id)
        counts["sections_created"] += 1
    db.flush()
    return counts


def main() -> int:
    database = None
    try:
        settings = Settings()
        credentials_path = os.environ.get("DEMO_CREDENTIALS_FILE")
        if not credentials_path:
            raise SeedError("DEMO_CREDENTIALS_FILE es obligatorio; no existen contraseñas predeterminadas.")
        credentials = load_credentials(Path(credentials_path))
        database = Database(settings)
        with database.session_factory() as db:
            with db.begin():
                database_name = db.scalar(text("SELECT current_database()"))
                if not isinstance(database_name, str) or "demo" not in database_name.lower():
                    raise SeedError("La semilla solo admite una base cuyo nombre identifique expresamente la demo.")
                result = seed_demo(db, credentials)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
    except (OSError, ValidationError, SQLAlchemyError):
        # No emitir tracebacks, DSN, valores recibidos ni errores de validación con contraseñas.
        print("No se completó la semilla. Revisa configuración, archivo de credenciales y migración; no se conservaron cambios parciales.", file=sys.stderr)
    finally:
        if database is not None:
            database.engine.dispose()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
