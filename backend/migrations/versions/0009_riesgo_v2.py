"""Bloque 8 (ADR 013): RIESGO_V2 sin participación junto a RIESGO_V1, que se conserva intacta."""
from pathlib import Path
from alembic import op

revision = '0009_riesgo_v2'
down_revision = '0008_real_chain'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execution_options(no_parameters=True).exec_driver_sql(
        Path(__file__).with_suffix('.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('0009 conserva referencias RIESGO_V2 inmutables; no admite downgrade destructivo.')
