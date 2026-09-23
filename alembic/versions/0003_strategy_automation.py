"""strategy automation
Revision ID: 0003_strategy_automation
Revises: 0002_live_risk_levels
"""
from alembic import op
import sqlalchemy as sa
revision='0003_strategy_automation'; down_revision='0002_live_risk_levels'; branch_labels=None; depends_on=None

def upgrade():
    # 0001 may create the current schema on a fresh installation.
    if 'strategies' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table('strategies',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('portfolio_id',sa.Integer(),sa.ForeignKey('portfolios.id'),nullable=False),
        sa.Column('name',sa.String(100),nullable=False),
        sa.Column('symbols',sa.Text(),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('min_confidence',sa.Float(),nullable=False,server_default='50'),
        sa.Column('position_size_pct',sa.Float(),nullable=False,server_default='10'),
        sa.Column('max_exposure_pct',sa.Float(),nullable=False,server_default='25'),
        sa.Column('max_open_positions',sa.Integer(),nullable=False,server_default='3'),
        sa.Column('cooldown_seconds',sa.Integer(),nullable=False,server_default='300'),
        sa.Column('total_orders',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('last_action',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
    )
    op.create_index('ix_strategies_portfolio_id','strategies',['portfolio_id'])

def downgrade():
    op.drop_index('ix_strategies_portfolio_id',table_name='strategies'); op.drop_table('strategies')
