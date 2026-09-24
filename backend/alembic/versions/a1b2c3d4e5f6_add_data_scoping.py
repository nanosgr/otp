"""add_data_scoping

Revision ID: a1b2c3d4e5f6
Revises: f5a6b7c8d9e0
Create Date: 2026-09-02 12:00:00.000000

Alcance de datos por permiso/rol:
- role_permissions.scope / scope_dimension
- tabla user_scopes (valores del usuario por dimensión)
- tabla orders (modelo de dominio de ejemplo; removible con scripts/remove_orders_domain.sh)
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = 'f5a6b7c8d9e0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'role_permissions',
        sa.Column('scope', sa.String(), nullable=False, server_default='all'),
    )
    op.add_column(
        'role_permissions',
        sa.Column('scope_dimension', sa.String(), nullable=True),
    )

    op.create_table(
        'user_scopes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('dimension', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'dimension', 'value', name='uq_user_scope'),
    )
    op.create_index(
        'ix_user_scopes_user_dimension', 'user_scopes', ['user_id', 'dimension']
    )


def downgrade() -> None:
    op.drop_index('ix_user_scopes_user_dimension', table_name='user_scopes')
    op.drop_table('user_scopes')
    op.drop_column('role_permissions', 'scope_dimension')
    op.drop_column('role_permissions', 'scope')
