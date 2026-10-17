"""M1 registro manual; conserva evidencia y contratos CSV anteriores."""
from pathlib import Path
from alembic import op

revision = '0005_manual_academic'
down_revision = '0004_followup'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execution_options(no_parameters=True).exec_driver_sql(
        Path(__file__).with_suffix('.sql').read_text(encoding='utf-8'))


def downgrade():
    raise RuntimeError('M1 conserva identidades y mediciones; no admite downgrade destructivo.')
