"""Bloque 1: mediciones MANUAL evaluables solo en SYNTHETIC."""
from pathlib import Path
from alembic import op

revision = '0006_manual_evaluable'
down_revision = '0005_manual_academic'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execution_options(no_parameters=True).exec_driver_sql(
        Path(__file__).with_suffix('.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('0006 conserva predicciones sobre mediciones manuales; no admite downgrade destructivo.')
