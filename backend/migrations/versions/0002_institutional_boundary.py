"""Límite institucional: no transforma ni elimina evidencia histórica."""
from alembic import op

revision = '0002_institutional_boundary'
down_revision = '0001_demo_schema'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # NOT VALID conserva registros históricos si se aplica a una base no vacía.
    # PostgreSQL impone la restricción a toda inserción/actualización posterior.
    for table in ('academic_periods', 'students', 'enrollments', 'import_batches',
                  'academic_snapshots', 'model_versions', 'predictions', 'alerts', 'interventions'):
        connection.exec_driver_sql(f"ALTER TABLE risk_school.{table} ADD CONSTRAINT institutional_origin CHECK (data_origin = 'REAL') NOT VALID")
        # En una base nueva queda validada; nunca se cambia la etiqueta de datos anteriores.
        if not connection.exec_driver_sql(f"SELECT EXISTS (SELECT 1 FROM risk_school.{table} WHERE data_origin <> 'REAL')").scalar():
            connection.exec_driver_sql(f'ALTER TABLE risk_school.{table} VALIDATE CONSTRAINT institutional_origin')
    for table in ('import_batches', 'academic_snapshots'):
        connection.exec_driver_sql(f"ALTER TABLE risk_school.{table} ALTER COLUMN schema_version SET DEFAULT 'academic-v1'")
    # No se publica activación de modelos. Restricción adicional, sin retirar la histórica.
    connection.exec_driver_sql('ALTER TABLE risk_school.model_versions ADD CONSTRAINT model_activation_pending CHECK (NOT is_active) NOT VALID')


def downgrade():
    raise RuntimeError('La transición no elimina restricciones ni evidencia mediante downgrade.')
