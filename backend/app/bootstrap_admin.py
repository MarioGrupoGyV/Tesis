"""Creación explícita del primer administrador, sin registro público ni contraseña persistida."""
import getpass
import sys
import warnings
from uuid import uuid4
from pydantic import BaseModel, EmailStr, Field, SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import Settings
from app.core.database import Database
from app.core.security import password_hash
from app.models.s1 import AppUser, AuditEvent


class AdministratorInput(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: SecretStr = Field(min_length=12, max_length=200)


class BootstrapError(Exception):
    pass


def create_first_admin(db, values: AdministratorInput):
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(21421001)"))
        if db.scalar(select(AppUser.id).where(AppUser.role == 'ADMIN').limit(1)):
            raise BootstrapError('Ya existe un administrador. No se creó ni modificó ninguna cuenta.')
        email, name = str(values.email).strip().lower(), values.display_name.strip()
        if not name or db.scalar(select(AppUser.id).where(AppUser.email == email)):
            raise BootstrapError('Nombre vacío o correo existente. No se modificó ninguna cuenta.')
        user = AppUser(id=uuid4(), email=email, display_name=name, role='ADMIN',
                       password_hash=password_hash(values.password.get_secret_value()), is_active=True)
        db.add(user)
        db.flush()
        db.add(AuditEvent(actor_id=user.id, entity_type='app_user', entity_id=user.id,
                         action='FIRST_ADMIN_CREATED', request_id=uuid4(), payload={'role':'ADMIN'}))
        db.flush()
        db.commit()
        return user.id
    except Exception:
        db.rollback()
        raise


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Ejecuta este comando en una terminal interactiva; no acepta contraseñas por argumentos o archivos.')
    try:
        email = input('Correo del administrador: ').strip()
        name = input('Nombre del administrador: ').strip()
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            password = getpass.getpass('Contraseña (mínimo 12 caracteres): ')
            if password != getpass.getpass('Repite la contraseña: '):
                raise BootstrapError('Las contraseñas no coinciden.')
        values = AdministratorInput(email=email, display_name=name, password=password)
        del password
        database = Database(Settings())
        try:
            with database.session_factory() as db:
                create_first_admin(db, values)
        finally:
            database.engine.dispose()
        print('Administrador creado. No se crearon periodos ni registros escolares.')
    except (BootstrapError, getpass.GetPassWarning) as exc:
        raise SystemExit(str(exc)) from None
    except ValidationError:
        raise SystemExit('Revisa correo, nombre y longitud de contraseña. No se guardaron cambios.') from None
    except SQLAlchemyError:
        raise SystemExit('No se pudo completar la creación. No se guardaron cambios; revisa conexión o duplicados.') from None


if __name__ == '__main__':
    main()
