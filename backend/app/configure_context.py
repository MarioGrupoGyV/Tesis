"""Configuración explícita por operador autenticado; no habilita procesamiento."""
import getpass
import sys
import warnings
from datetime import date
from uuid import UUID, uuid4
from pydantic import BaseModel, EmailStr, Field, SecretStr, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import Settings
from app.core.database import Database
from app.core.security import password_hash, password_verify
from app.models.s1 import AppUser, AcademicPeriod, GradeSection, AuditEvent
from app.bootstrap_admin import BootstrapError


class PeriodInput(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    school_year: int = Field(ge=2000, le=2100)
    start_date: date
    end_date: date

    @model_validator(mode='after')
    def dates(self):
        if self.end_date <= self.start_date or self.start_date.year != self.school_year or self.end_date.year != self.school_year:
            raise ValueError('Las fechas deben estar ordenadas y pertenecer al año escolar indicado.')
        return self


class SectionInput(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    grade: int = Field(ge=1, le=5)
    school_year: int = Field(ge=2000, le=2100)
    tutor_id: UUID | None


class UserInput(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    role: str
    password: SecretStr = Field(min_length=12, max_length=200)


def configure(db, actor, values):
    try:
        if actor.role != 'ADMIN' or not actor.is_active:
            raise BootstrapError('Se requiere un administrador activo.')
        if isinstance(values, PeriodInput):
            record = AcademicPeriod(**values.model_dump(), data_origin='REAL', is_locked=False)
        elif isinstance(values, SectionInput):
            if not db.scalar(select(AcademicPeriod.id).where(AcademicPeriod.school_year == values.school_year, AcademicPeriod.data_origin == 'REAL').limit(1)):
                raise BootstrapError('Configura primero el periodo del año indicado.')
            if values.tutor_id:
                tutor = db.get(AppUser, values.tutor_id)
                if not tutor or tutor.role != 'TUTOR' or not tutor.is_active:
                    raise BootstrapError('Indica el UUID de un tutor activo.')
            record = GradeSection(**values.model_dump())
        else:
            if values.role not in ('TUTOR','DIRECTOR','RESEARCHER') or not values.display_name.strip():
                raise BootstrapError('Indica nombre y rol TUTOR, DIRECTOR o RESEARCHER.')
            record = AppUser(email=str(values.email).lower(), display_name=values.display_name.strip(), role=values.role,
                password_hash=password_hash(values.password.get_secret_value()), is_active=True)
        db.add(record)
        db.flush()
        db.add(AuditEvent(actor_id=actor.id, entity_type=record.__tablename__, entity_id=record.id,
            action='CONTEXT_CONFIGURED', request_id=uuid4(), payload={}))
        db.commit()
        return record.id
    except Exception:
        db.rollback()
        raise


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Se requiere terminal interactiva; no se admiten contraseñas por argumentos.')
    try:
        warnings.simplefilter('error', getpass.GetPassWarning)
        email = input('Correo del administrador: ').strip().lower()
        password = getpass.getpass('Contraseña del administrador: ')
        database = Database(Settings())
        try:
            with database.session_factory() as db:
                actor = db.scalar(select(AppUser).where(AppUser.email == email, AppUser.role == 'ADMIN', AppUser.is_active.is_(True)))
                if not actor or not password_verify(password, actor.password_hash):
                    raise BootstrapError('Acceso no autorizado.')
                del password
                kind = input('Crear periodo, seccion o usuario: ').strip()
                if kind == 'periodo':
                    values = PeriodInput(code=input('Código: ').strip(), school_year=input('Año escolar: '), start_date=input('Inicio YYYY-MM-DD: '), end_date=input('Fin YYYY-MM-DD: '))
                elif kind == 'seccion':
                    values = SectionInput(code=input('Código de sección: ').strip(), grade=input('Grado: '), school_year=input('Año escolar: '), tutor_id=input('UUID del tutor (vacío sin asignar): ').strip() or None)
                elif kind == 'usuario':
                    email = input('Correo: ').strip()
                    name = input('Nombre: ').strip()
                    role = input('Rol TUTOR, DIRECTOR o RESEARCHER: ').strip()
                    password = getpass.getpass('Contraseña de la nueva cuenta: ')
                    if password != getpass.getpass('Repite la contraseña: '):
                        raise BootstrapError('Las contraseñas no coinciden.')
                    values = UserInput(email=email, display_name=name, role=role, password=password)
                    del password
                else:
                    raise BootstrapError('Acción no reconocida; sin cambios.')
                print('Registro creado: '+str(configure(db, actor, values)))
        finally:
            database.engine.dispose()
    except (BootstrapError, getpass.GetPassWarning) as exc:
        raise SystemExit(str(exc)) from None
    except (ValidationError, SQLAlchemyError):
        raise SystemExit('No se guardaron cambios: revisa valores, duplicados, relaciones o conexión.') from None


if __name__ == '__main__':
    main()
