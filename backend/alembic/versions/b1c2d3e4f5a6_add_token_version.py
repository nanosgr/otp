"""add_token_version

Revision ID: b1c2d3e4f5a6
Revises: 94ddaa0db312
Create Date: 2026-04-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = '94ddaa0db312'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('users', 'token_version')
