"""liquidación proyectada: datos del expediente, cómputo, imputación, encasillamiento y escalafón de los conceptos

Revision ID: f1a2b3c4d5e6
Revises: e9f0a1b2c3d4
Create Date: 2026-10-01 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e9f0a1b2c3d4'
branch_labels = None
depends_on = None

STR = sqlmodel.sql.sqltypes.AutoString


def _ts():
    return [
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    ]


def upgrade() -> None:
    op.create_table(
        'computo_servicios',
        sa.Column('causante_id', sa.Integer(), nullable=False),
        sa.Column('concepto', STR(), nullable=False),
        sa.Column('anios', sa.Integer(), nullable=False),
        sa.Column('meses', sa.Integer(), nullable=False),
        sa.Column('dias', sa.Integer(), nullable=False),
        sa.Column('observacion', STR(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(['causante_id'], ['causantes.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_computo_servicios_causante_id'), 'computo_servicios', ['causante_id'], unique=False)
    op.create_table(
        'encasillamiento',
        sa.Column('cargo_id', sa.Integer(), nullable=False),
        sa.Column('codigo', STR(), nullable=False),
        sa.Column('descripcion', STR(), nullable=True),
        sa.Column('valor', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('aplica', sa.Boolean(), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(['cargo_id'], ['cargos_secuencia.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('cargo_id', 'codigo', name='uq_encasillamiento_cargo_codigo'),
    )
    op.create_index(op.f('ix_encasillamiento_cargo_id'), 'encasillamiento', ['cargo_id'], unique=False)

    for col in ('zona_cargo_base', 'grado', 'unidad_organizativa', 'regimen_salarial', 'agrupamiento', 'tramo', 'subtramo'):
        op.add_column('cargos_secuencia', sa.Column(col, STR(), nullable=True))
    for col in ('cuil', 'grado', 'cuerpo', 'condicion', 'familia'):
        op.add_column('causantes', sa.Column(col, STR(), nullable=True))
    for col in ('fecha_renuncia_condicionada', 'cuadro_servicio_desde', 'cuadro_servicio_hasta'):
        op.add_column('causantes', sa.Column(col, sa.Date(), nullable=True))
    op.execute("UPDATE causantes SET escalafon = 'policia' WHERE escalafon IS NULL OR escalafon NOT IN ('policia', 'penitenciario')")
    op.alter_column('causantes', 'escalafon', existing_type=sa.VARCHAR(), nullable=False)

    # conceptos: un juego de reglas por escalafón (el código es único dentro del escalafón)
    op.add_column('conceptos', sa.Column('escalafon', STR(), nullable=False, server_default='policia'))
    op.alter_column('conceptos', 'escalafon', server_default=None)
    op.drop_index(op.f('ix_conceptos_codigo'), table_name='conceptos')
    op.create_index(op.f('ix_conceptos_codigo'), 'conceptos', ['codigo'], unique=False)
    op.create_unique_constraint('uq_conceptos_codigo_escalafon', 'conceptos', ['codigo', 'escalafon'])

    op.add_column('liquidaciones', sa.Column('modalidad', STR(), nullable=False, server_default='retroactivo'))
    op.alter_column('liquidaciones', 'modalidad', server_default=None)
    op.add_column('liquidaciones', sa.Column('asunto', STR(), nullable=True))
    op.add_column('recibo_conceptos', sa.Column('unitario', sa.Numeric(precision=18, scale=4), nullable=True))


def downgrade() -> None:
    op.drop_column('recibo_conceptos', 'unitario')
    op.drop_column('liquidaciones', 'asunto')
    op.drop_column('liquidaciones', 'modalidad')
    op.execute("DELETE FROM conceptos WHERE escalafon <> 'policia'")
    op.drop_constraint('uq_conceptos_codigo_escalafon', 'conceptos', type_='unique')
    op.drop_index(op.f('ix_conceptos_codigo'), table_name='conceptos')
    op.create_index(op.f('ix_conceptos_codigo'), 'conceptos', ['codigo'], unique=True)
    op.drop_column('conceptos', 'escalafon')
    op.alter_column('causantes', 'escalafon', existing_type=sa.VARCHAR(), nullable=True)
    for col in ('cuadro_servicio_hasta', 'cuadro_servicio_desde', 'fecha_renuncia_condicionada',
                'familia', 'condicion', 'cuerpo', 'grado', 'cuil'):
        op.drop_column('causantes', col)
    for col in ('subtramo', 'tramo', 'agrupamiento', 'regimen_salarial', 'unidad_organizativa', 'grado', 'zona_cargo_base'):
        op.drop_column('cargos_secuencia', col)
    op.drop_index(op.f('ix_encasillamiento_cargo_id'), table_name='encasillamiento')
    op.drop_table('encasillamiento')
    op.drop_index(op.f('ix_computo_servicios_causante_id'), table_name='computo_servicios')
    op.drop_table('computo_servicios')
