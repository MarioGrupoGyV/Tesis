"""13 tablas del contrato DEMO 0.1.1 y permisos mínimos de aplicación."""
from pathlib import Path
from alembic import op

revision = '0001_demo_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    sql_path = Path(__file__).with_suffix('.sql')
    sql = sql_path.read_text(encoding='utf-8')
    # El snapshot vive con la revisión: cambios futuros requieren nueva migración.
    op.get_bind().execution_options(no_parameters=True).exec_driver_sql(sql)
    op.get_bind().exec_driver_sql('''
        REVOKE ALL ON SCHEMA risk_school FROM PUBLIC;
        GRANT USAGE ON SCHEMA risk_school TO riesgo_app;
        GRANT SELECT ON ALL TABLES IN SCHEMA risk_school TO riesgo_app;
        GRANT INSERT ON ALL TABLES IN SCHEMA risk_school TO riesgo_app;
        GRANT UPDATE ON risk_school.app_users, risk_school.user_sessions,
          risk_school.academic_periods, risk_school.grade_sections,
          risk_school.students, risk_school.enrollments, risk_school.import_batches,
          risk_school.model_versions, risk_school.alerts, risk_school.interventions TO riesgo_app;
        REVOKE ALL ON ALL FUNCTIONS IN SCHEMA risk_school FROM PUBLIC;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA risk_school TO riesgo_app;
    ''')


def downgrade():
    raise RuntimeError('No se elimina evidencia DEMO por downgrade. Crear una base de prueba nueva.')
