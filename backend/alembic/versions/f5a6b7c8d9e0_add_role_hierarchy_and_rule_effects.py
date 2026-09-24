"""add_role_hierarchy_and_rule_effects

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'role_parents',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'parent_id'),
    )
    op.add_column(
        'role_permissions',
        sa.Column('effect', sa.String(), nullable=False, server_default='allow'),
    )
    op.add_column(
        'role_permissions',
        sa.Column('assertion', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('role_permissions', 'assertion')
    op.drop_column('role_permissions', 'effect')
    op.drop_table('role_parents')
