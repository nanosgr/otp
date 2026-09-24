"""pensión de dos cargos: peso de secuencia y secuencia del concepto de recibo

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-09-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e9f0a1b2c3d4'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cargos_secuencia', sa.Column('porcentaje_secuencia', sa.Numeric(18, 4), nullable=False, server_default='100'))
    op.alter_column('cargos_secuencia', 'porcentaje_secuencia', server_default=None)
    op.add_column('recibo_conceptos', sa.Column('secuencia', sa.Integer(), nullable=True))
    # Los conceptos de retiro y pensión sembrados pasan a la etapa "beneficio", que calcula sobre el haber ponderado
    # de los cargos. Solo se tocan los que siguen con la definición original (sin ediciones manuales).
    op.execute("""
        UPDATE conceptos
           SET etapa = 'beneficio',
               formula_importe = REPLACE(formula_importe, 'TOTAL(''REMUNERATIVO'')', 'HABER_PONDERADO')
         WHERE codigo IN ('HABER_RETIRO', 'PENSION_TOTAL', 'PENSION_BENEFICIARIO', 'ART37') AND etapa = 'haber'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE conceptos
           SET etapa = 'haber',
               formula_importe = REPLACE(formula_importe, 'HABER_PONDERADO', 'TOTAL(''REMUNERATIVO'')')
         WHERE codigo IN ('HABER_RETIRO', 'PENSION_TOTAL', 'PENSION_BENEFICIARIO', 'ART37') AND etapa = 'beneficio'
    """)
    op.drop_column('recibo_conceptos', 'secuencia')
    op.drop_column('cargos_secuencia', 'porcentaje_secuencia')
