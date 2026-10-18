"""Bloque 3B-1: protocolo REAL, referencias de riesgo y relojes retrospectivos (sin cambiar comportamiento)."""
from pathlib import Path
from alembic import op

revision = '0007_real_protocol'
down_revision = '0006_manual_evaluable'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execution_options(no_parameters=True).exec_driver_sql(
        Path(__file__).with_suffix('.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('0007 conserva protocolos y referencias de riesgo; no admite downgrade destructivo.')
