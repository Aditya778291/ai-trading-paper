"""Add audit events and order idempotency keys."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from src.api.database import Base
from src.api import models, audit
revision='0001'; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    bind=op.get_bind(); insp=inspect(bind)
    # Fresh installations: create the complete current schema, including this revision's fields.
    if 'users' not in insp.get_table_names():
        Base.metadata.create_all(bind=bind)
        return
    if 'audit_events' not in insp.get_table_names():
        op.create_table('audit_events', sa.Column('id',sa.Integer(),primary_key=True), sa.Column('user_id',sa.Integer(),nullable=True), sa.Column('event',sa.String(64),nullable=False), sa.Column('request_id',sa.String(64),nullable=True), sa.Column('detail',sa.Text(),nullable=True), sa.Column('timestamp',sa.DateTime(timezone=True),nullable=False), sa.ForeignKeyConstraint(['user_id'],['users.id']))
        for name,col in [('ix_audit_events_user_id','user_id'),('ix_audit_events_event','event'),('ix_audit_events_request_id','request_id'),('ix_audit_events_timestamp','timestamp')]: op.create_index(name,'audit_events',[col])
    if 'idempotency_key' not in {c['name'] for c in insp.get_columns('orders')}:
        op.add_column('orders', sa.Column('idempotency_key',sa.String(128),nullable=True))
        op.create_index('ix_orders_idempotency_key','orders',['idempotency_key'],unique=True)

def downgrade():
    bind=op.get_bind(); insp=inspect(bind)
    if 'orders' in insp.get_table_names() and 'idempotency_key' in {c['name'] for c in insp.get_columns('orders')}:
        op.drop_index('ix_orders_idempotency_key', table_name='orders'); op.drop_column('orders','idempotency_key')
    if 'audit_events' in insp.get_table_names(): op.drop_table('audit_events')
