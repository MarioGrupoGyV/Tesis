"""Bloque 3B-2: cadena REAL (estudios, procedencia, modelo activo por alcance, triggers y elegibilidad por protocolo)."""
from pathlib import Path
from alembic import op

revision = '0008_real_chain'
down_revision = '0007_real_protocol'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execution_options(no_parameters=True).exec_driver_sql(
        Path(__file__).with_suffix('.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('0008 conserva estudios, modelos y seguimiento REAL; no admite downgrade destructivo.')
