import os
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool


def migration_url():
    file = os.environ.get('MIGRATION_DATABASE_URL_FILE')
    url = Path(file).read_text(encoding='utf-8').strip() if file else os.environ.get('MIGRATION_DATABASE_URL')
    if not url:
        raise RuntimeError('Configurar MIGRATION_DATABASE_URL_FILE o MIGRATION_DATABASE_URL.')
    if not url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Las migraciones requieren PostgreSQL y el driver psycopg acordado.')
    return url


if context.is_offline_mode():
    context.configure(url=migration_url(), target_metadata=None, literal_binds=True,
                      dialect_opts={'paramstyle': 'named'})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(migration_url(), poolclass=pool.NullPool, echo=False,
                           hide_parameters=True, connect_args={'connect_timeout': 5})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
