"""add position risk levels

Revision ID: 0002_live_risk_levels
Revises: 0001_production_hardening
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_live_risk_levels'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    # 0001 may create the current schema on a fresh installation, so only add
    # risk columns when upgrading an older database that does not have them.
    bind = op.get_bind()
    columns = {c['name'] for c in sa.inspect(bind).get_columns('positions')}
    if 'stop_loss' not in columns:
        op.add_column('positions', sa.Column('stop_loss', sa.Float(), nullable=True))
    if 'take_profit' not in columns:
        op.add_column('positions', sa.Column('take_profit', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('positions', 'take_profit')
    op.drop_column('positions', 'stop_loss')
