"""enrich_audit_logs

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-26 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('request_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('audit_logs', sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='success'))
    op.add_column('audit_logs', sa.Column('before_data', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('audit_logs', sa.Column('after_data', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('audit_logs', sa.Column('subject_id', sa.Integer(), nullable=True))
    op.add_column('audit_logs', sa.Column('user_agent', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_logs', 'user_agent')
    op.drop_column('audit_logs', 'subject_id')
    op.drop_column('audit_logs', 'after_data')
    op.drop_column('audit_logs', 'before_data')
    op.drop_column('audit_logs', 'status')
    op.drop_column('audit_logs', 'request_id')
