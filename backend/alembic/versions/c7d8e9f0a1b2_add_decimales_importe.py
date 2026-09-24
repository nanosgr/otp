"""add decimales_importe a conceptos

Revision ID: c7d8e9f0a1b2
Revises: b5983b73acf4
Create Date: 2026-09-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'b5983b73acf4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('conceptos', sa.Column('decimales_importe', sa.Integer(), nullable=False, server_default='2'))
    op.alter_column('conceptos', 'decimales_importe', server_default=None)


def downgrade() -> None:
    op.drop_column('conceptos', 'decimales_importe')
