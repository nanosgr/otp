"""fase 3: etapa de conceptos, tablas versionadas, cargo como DATOS, totales de liquidación

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-09-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def _money():
    return sa.Numeric(18, 4)


def upgrade() -> None:
    # conceptos.etapa
    op.add_column('conceptos', sa.Column('etapa', sa.String(), nullable=False, server_default='haber'))
    op.alter_column('conceptos', 'etapa', server_default=None)

    # tablas: el código deja de ser único; es único por (código, vigencia_desde)
    op.drop_index('ix_tablas_codigo', table_name='tablas')
    op.create_index('ix_tablas_codigo', 'tablas', ['codigo'], unique=False)
    op.create_unique_constraint('uq_tablas_codigo_vigencia', 'tablas', ['codigo', 'vigencia_desde'])

    # cargos_secuencia: porcentajes tipeados como en DATOS
    for col in ('responsabilidad_jerarquica_porcentaje', 'recargo_servicio_porcentaje', 'cuerpo_apoyo_porcentaje'):
        op.add_column('cargos_secuencia', sa.Column(col, _money(), nullable=False, server_default='0'))
        op.alter_column('cargos_secuencia', col, server_default=None)
    op.add_column('cargos_secuencia', sa.Column('zona_clase', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('cargos_secuencia', 'zona_clase', server_default=None)
    for col in ('responsabilidad_jerarquica', 'recargo_servicio', 'cuerpo_apoyo'):
        op.drop_column('cargos_secuencia', col)

    # liquidaciones: anticipo y totales
    for col in ('anticipo_importe', 'total_credito', 'total_debitos', 'total_liquido'):
        op.add_column('liquidaciones', sa.Column(col, _money(), nullable=False, server_default='0'))
        op.alter_column('liquidaciones', col, server_default=None)
    op.add_column('liquidaciones', sa.Column('calculada_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('liquidaciones', 'calculada_at')
    for col in ('total_liquido', 'total_debitos', 'total_credito', 'anticipo_importe'):
        op.drop_column('liquidaciones', col)

    for col in ('responsabilidad_jerarquica', 'recargo_servicio', 'cuerpo_apoyo'):
        op.add_column('cargos_secuencia', sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column('cargos_secuencia', col, server_default=None)
    op.drop_column('cargos_secuencia', 'zona_clase')
    for col in ('cuerpo_apoyo_porcentaje', 'recargo_servicio_porcentaje', 'responsabilidad_jerarquica_porcentaje'):
        op.drop_column('cargos_secuencia', col)

    op.drop_constraint('uq_tablas_codigo_vigencia', 'tablas', type_='unique')
    op.drop_index('ix_tablas_codigo', table_name='tablas')
    op.create_index('ix_tablas_codigo', 'tablas', ['codigo'], unique=True)

    op.drop_column('conceptos', 'etapa')
