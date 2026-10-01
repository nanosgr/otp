"""Modelos del dominio previsional (retiros/jubilaciones y pensiones policiales).

Convención: `XBase` (campos editables, también schema de creación), `X` (tabla).
Los schemas de lectura/actualización se derivan en `app.api.crud_router`.
Los importes usan Numeric(18,4); las reglas temporales usan vigencia_desde/hasta.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, List, Optional

from pydantic import StringConstraints
from sqlalchemy import JSON, Column, DateTime, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel

JSONType = JSON().with_variant(JSONB(), "postgresql")

# Valores permitidos (se validan con `StringConstraints` en los schemas de entrada)
PARENTESCOS = "^(conyuge|hijo|padre|madre|conviviente|otro)$"
T_PARENTESCOS = Annotated[str, StringConstraints(pattern=PARENTESCOS)]
COLUMNAS_CONCEPTO = "^(REMUNERATIVO|NO_REMUNERATIVO|DESCUENTO|CONTRIBUCION|AUXILIAR)$"
T_COLUMNAS_CONCEPTO = Annotated[str, StringConstraints(pattern=COLUMNAS_CONCEPTO)]
ALCANCES = "^(general|grupo|tipo_beneficio)$"
T_ALCANCES = Annotated[str, StringConstraints(pattern=ALCANCES)]
TIPOS_BENEFICIO = "^(retiro|pension)$"
T_TIPOS_BENEFICIO = Annotated[str, StringConstraints(pattern=TIPOS_BENEFICIO)]
TIPOS_LIQUIDACION = "^(retiro|pension|reajuste)$"
T_TIPOS_LIQUIDACION = Annotated[str, StringConstraints(pattern=TIPOS_LIQUIDACION)]
ESTADOS_LIQUIDACION = "^(ABIERTA|CERRADA)$"
T_ESTADOS_LIQUIDACION = Annotated[str, StringConstraints(pattern=ESTADOS_LIQUIDACION)]
TIPOS_DATO = "^(decimal|int|text|date|bool)$"
T_TIPOS_DATO = Annotated[str, StringConstraints(pattern=TIPOS_DATO)]
TIPOS_PERSONAL = "^(subalterno|superior)$"
T_TIPOS_PERSONAL = Annotated[str, StringConstraints(pattern=TIPOS_PERSONAL)]
TIPOS_SERVICIO = "^(servicio|suspension|licencia|otro)$"
T_TIPOS_SERVICIO = Annotated[str, StringConstraints(pattern=TIPOS_SERVICIO)]
TITULOS = "^(ninguno|pregrado|grado|posgrado)$"
T_TITULOS = Annotated[str, StringConstraints(pattern=TITULOS)]
ETAPAS = "^(haber|beneficio|liquidacion)$"
T_ETAPAS = Annotated[str, StringConstraints(pattern=ETAPAS)]
ESCALAFONES = "^(policia|penitenciario)$"
T_ESCALAFONES = Annotated[str, StringConstraints(pattern=ESCALAFONES)]
MODALIDADES = "^(retroactivo|proyectada)$"
T_MODALIDADES = Annotated[str, StringConstraints(pattern=MODALIDADES)]
CONCEPTOS_COMPUTO = "^(cuadro_servicio|hasta_renuncia|servicios_adicionales|beneficio_titulo|suspensiones)$"
T_CONCEPTOS_COMPUTO = Annotated[str, StringConstraints(pattern=CONCEPTOS_COMPUTO)]
TRAMOS = "^(01|02)$"
T_TRAMOS = Annotated[str, StringConstraints(pattern=TRAMOS)]
PERIODO = r"^\d{4}-(0[1-9]|1[0-2])$"
T_PERIODO = Annotated[str, StringConstraints(pattern=PERIODO)]


def _created_at() -> Any:
    return Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now()))


def _updated_at() -> Any:
    return Field(default=None, sa_column=Column(DateTime(timezone=True), onupdate=func.now(), nullable=True))


def _money(default: Optional[Decimal] = Decimal("0")) -> Any:
    return Field(default=default, sa_type=Numeric(18, 4))


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

class CausanteBase(SQLModel):
    expediente: Optional[str] = None
    dni: str = Field(index=True)
    apellido: str
    nombre: str
    fecha_nacimiento: Optional[date] = None
    fecha_fallecimiento: Optional[date] = None
    fecha_ingreso: Optional[date] = None
    fecha_egreso: Optional[date] = None
    escalafon: T_ESCALAFONES = "policia"
    tipo_personal: T_TIPOS_PERSONAL = "subalterno"
    # 1. Datos del expediente (liquidación proyectada de retiro)
    cuil: Optional[str] = None
    grado: Optional[str] = None
    cuerpo: Optional[str] = None
    condicion: Optional[str] = None
    familia: Optional[str] = None
    fecha_renuncia_condicionada: Optional[date] = None
    cuadro_servicio_desde: Optional[date] = None
    cuadro_servicio_hasta: Optional[date] = None
    is_active: bool = True


class Causante(CausanteBase, table=True):
    __tablename__ = "causantes"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class BeneficiarioBase(SQLModel):
    causante_id: int = Field(foreign_key="causantes.id", index=True, ondelete="CASCADE")
    apellido: str
    nombre: str
    dni: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    parentesco: T_PARENTESCOS = "conyuge"
    porcentaje: Decimal = _money(Decimal("0"))
    fecha_alta: Optional[date] = None
    fecha_baja: Optional[date] = None
    discapacidad: bool = False
    art37: bool = False
    is_active: bool = True


class Beneficiario(BeneficiarioBase, table=True):
    __tablename__ = "beneficiarios"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class CargoSecuenciaBase(SQLModel):
    causante_id: int = Field(foreign_key="causantes.id", index=True, ondelete="CASCADE")
    secuencia: int = 1
    # peso de la secuencia en el haber ponderado (DATOS: "PORCENTAJE DE SECUENCIAS"); la suma de los cargos debe ser 100
    porcentaje_secuencia: Decimal = _money(Decimal("100"))
    clase: int = Field(default=2, ge=1, le=27)
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    # porcentajes tal como se cargan en la hoja DATOS (0-100)
    responsabilidad_jerarquica_porcentaje: Decimal = _money()
    recargo_servicio_porcentaje: Decimal = _money()
    titulo: T_TITULOS = "ninguno"
    titulo_pregrado_nivel: int = Field(default=0, ge=0, le=3)
    riesgo_especial: bool = False
    zona_porcentaje: Decimal = _money()
    zona_clase: int = Field(default=0, ge=0, le=27)
    # cargo cuya clase es la base de la zona (anexo de zona), solo informativo
    zona_cargo_base: Optional[str] = None
    anios_antiguedad: Decimal = _money()
    presentismo: bool = False
    cuerpo_apoyo_porcentaje: Decimal = _money()
    adicional_seguridad: bool = False
    eventos_especiales: bool = False
    porcentaje_retiro: Decimal = _money()
    # 3. Imputación / codificación previsional
    grado: Optional[str] = None
    caracter: Optional[str] = None
    jurisdiccion: Optional[str] = None
    unidad_organizativa: Optional[str] = None
    finalidad: Optional[str] = None
    funcion: Optional[str] = None
    regimen_salarial: Optional[str] = None   # R.S.: 36 policía, 37 penitenciaría
    agrupamiento: Optional[str] = None       # A.: 1 seguridad, 2 administrativo
    tramo: Optional[T_TRAMOS] = None         # T.: 01 subalterno, 02 superior
    subtramo: Optional[str] = None           # ST.: según clase


class CargoSecuencia(CargoSecuenciaBase, table=True):
    __tablename__ = "cargos_secuencia"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class EncasillamientoItemBase(SQLModel):
    """4. Encasillamiento definitivo: valor por concepto del cargo. Llega al motor como `campos[codigo].unidad`.

    `aplica=False` es el "-" de la planilla; `aplica=True` sin valor es el "$" (aplica el monto fijo).
    """
    cargo_id: int = Field(foreign_key="cargos_secuencia.id", index=True, ondelete="CASCADE")
    codigo: str
    descripcion: Optional[str] = None
    valor: Optional[Decimal] = Field(default=None, sa_type=Numeric(18, 4))
    aplica: bool = True
    orden: int = 0


class EncasillamientoItem(EncasillamientoItemBase, table=True):
    __tablename__ = "encasillamiento"
    __table_args__ = (UniqueConstraint("cargo_id", "codigo", name="uq_encasillamiento_cargo_codigo"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ComputoServicioBase(SQLModel):
    """2. Cómputo de servicios: una fila por concepto (años/meses/días); los totales se calculan (services/computo.py)."""
    causante_id: int = Field(foreign_key="causantes.id", index=True, ondelete="CASCADE")
    concepto: T_CONCEPTOS_COMPUTO = "cuadro_servicio"
    anios: int = 0
    meses: int = 0
    dias: int = 0
    observacion: Optional[str] = None
    orden: int = 0


class ComputoServicio(ComputoServicioBase, table=True):
    __tablename__ = "computo_servicios"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ServicioPeriodoBase(SQLModel):
    causante_id: int = Field(foreign_key="causantes.id", index=True, ondelete="CASCADE")
    tipo: T_TIPOS_SERVICIO = "servicio"
    fecha_desde: date
    fecha_hasta: Optional[date] = None
    descripcion: Optional[str] = None
    computable: bool = True


class ServicioPeriodo(ServicioPeriodoBase, table=True):
    __tablename__ = "servicios_periodo"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ZonaDestinoBase(SQLModel):
    causante_id: int = Field(foreign_key="causantes.id", index=True, ondelete="CASCADE")
    dependencia: str
    porcentaje_zona: Decimal = _money()
    fecha_desde: date
    fecha_hasta: Optional[date] = None


class ZonaDestino(ZonaDestinoBase, table=True):
    __tablename__ = "zonas_destino"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


# ---------------------------------------------------------------------------
# Catálogo de conceptos y reglas
# ---------------------------------------------------------------------------

class ConceptoGrupoLink(SQLModel, table=True):
    __tablename__ = "concepto_grupo"

    grupo_id: Optional[int] = Field(default=None, foreign_key="grupos_concepto.id", primary_key=True, ondelete="CASCADE")
    concepto_id: Optional[int] = Field(default=None, foreign_key="conceptos.id", primary_key=True, ondelete="CASCADE")


class ConceptoBase(SQLModel):
    codigo: str = Field(index=True)
    # juego de reglas: el liquidador pasa al motor solo los conceptos del escalafón del causante
    escalafon: T_ESCALAFONES = "policia"
    descripcion: str
    columna: T_COLUMNAS_CONCEPTO = "REMUNERATIVO"
    formula_unidad: Optional[str] = None
    formula_importe: Optional[str] = None
    formula_unitario: Optional[str] = None
    formula_condicion: Optional[str] = None
    simbolo_unidad: Optional[str] = None
    decimales_unidad: int = Field(default=4, ge=0, le=10)
    decimales_importe: int = Field(default=2, ge=0, le=10)
    unidad_visible: bool = True
    # "haber": se calcula por tramo mensual; "liquidacion": se calcula una vez sobre el subtotal (descuentos, anticipos)
    etapa: T_ETAPAS = "haber"
    orden: int = 0
    is_active: bool = True


class Concepto(ConceptoBase, table=True):
    __tablename__ = "conceptos"
    __table_args__ = (UniqueConstraint("codigo", "escalafon", name="uq_conceptos_codigo_escalafon"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class GrupoConceptoBase(SQLModel):
    nombre: str = Field(index=True, unique=True)
    descripcion: Optional[str] = None
    is_active: bool = True


class GrupoConcepto(GrupoConceptoBase, table=True):
    __tablename__ = "grupos_concepto"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class FormulaAuxiliarBase(SQLModel):
    codigo: str = Field(index=True, unique=True)
    descripcion: Optional[str] = None
    formato: Optional[str] = None
    formula: str
    orden: int = 0


class FormulaAuxiliar(FormulaAuxiliarBase, table=True):
    __tablename__ = "formulas_auxiliares"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ConceptoVigenciaBase(SQLModel):
    concepto_id: int = Field(foreign_key="conceptos.id", index=True, ondelete="CASCADE")
    alcance: T_ALCANCES = "general"
    grupo_id: Optional[int] = Field(default=None, foreign_key="grupos_concepto.id", ondelete="CASCADE")
    tipo_beneficio: Optional[T_TIPOS_BENEFICIO] = None
    vigencia_desde: Optional[date] = None
    vigencia_hasta: Optional[date] = None
    descripcion: Optional[str] = None
    orden: Optional[int] = None


class ConceptoVigencia(ConceptoVigenciaBase, table=True):
    __tablename__ = "concepto_vigencias"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class TablaBase(SQLModel):
    codigo: str = Field(index=True)
    descripcion: Optional[str] = None
    # [{"nombre": "CLASE", "tipo": "int"}, ...]
    columnas: List[Any] = Field(default_factory=list, sa_type=JSONType)
    vigencia_desde: Optional[date] = None
    vigencia_hasta: Optional[date] = None
    is_active: bool = True


class Tabla(TablaBase, table=True):
    __tablename__ = "tablas"
    __table_args__ = (UniqueConstraint("codigo", "vigencia_desde", name="uq_tablas_codigo_vigencia"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class FilaBase(SQLModel):
    tabla_id: int = Field(foreign_key="tablas.id", index=True, ondelete="CASCADE")
    orden: int = 0
    # lista de valores alineada con Tabla.columnas
    valores: List[Any] = Field(default_factory=list, sa_type=JSONType)


class Fila(FilaBase, table=True):
    __tablename__ = "filas"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ParametroHistorialBase(SQLModel):
    campo: str = Field(index=True)
    valor: str
    tipo_dato: T_TIPOS_DATO = "decimal"
    vigencia_desde: Optional[date] = None
    vigencia_hasta: Optional[date] = None
    descripcion: Optional[str] = None


class ParametroHistorial(ParametroHistorialBase, table=True):
    __tablename__ = "parametros_historial"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


# ---------------------------------------------------------------------------
# Liquidación
# ---------------------------------------------------------------------------

class LiquidacionBase(SQLModel):
    causante_id: int = Field(foreign_key="causantes.id", index=True)
    periodo: T_PERIODO = Field(index=True)
    tipo: T_TIPOS_LIQUIDACION = "retiro"
    # "proyectada": haber de un mes base (periodo) x % de retiro, sin retroactivo, SAC ni descuentos
    modalidad: T_MODALIDADES = "retroactivo"
    asunto: Optional[str] = None
    estado: T_ESTADOS_LIQUIDACION = "ABIERTA"
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    fecha_pago: Optional[date] = None
    observaciones: Optional[str] = None
    # anticipo ya percibido, se descuenta en el líquido
    anticipo_importe: Decimal = _money()


class Liquidacion(LiquidacionBase, table=True):
    __tablename__ = "liquidaciones"

    id: Optional[int] = Field(default=None, primary_key=True)
    total_credito: Decimal = _money()
    total_debitos: Decimal = _money()
    total_liquido: Decimal = _money()
    calculada_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_by: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ReciboBase(SQLModel):
    liquidacion_id: int = Field(foreign_key="liquidaciones.id", index=True, ondelete="CASCADE")
    beneficiario_id: Optional[int] = Field(default=None, foreign_key="beneficiarios.id")
    numero: int = 1
    total_remunerativo: Decimal = _money()
    total_no_remunerativo: Decimal = _money()
    total_descuento: Decimal = _money()
    total_contribucion: Decimal = _money()
    sueldo_bruto: Decimal = _money()
    sueldo_neto: Decimal = _money()
    # foto del causante/beneficiario/cargo y parámetros usados al liquidar
    snapshot: Optional[Any] = Field(default=None, sa_type=JSONType)


class Recibo(ReciboBase, table=True):
    __tablename__ = "recibos"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class ReciboConceptoBase(SQLModel):
    recibo_id: int = Field(foreign_key="recibos.id", index=True, ondelete="CASCADE")
    concepto_id: Optional[int] = Field(default=None, foreign_key="conceptos.id")
    # secuencia (cargo) a la que pertenece el concepto; None para los de beneficio y liquidación
    secuencia: Optional[int] = None
    codigo: str
    descripcion: str
    columna: T_COLUMNAS_CONCEPTO = "REMUNERATIVO"
    unidad: Optional[Decimal] = Field(default=None, sa_type=Numeric(18, 4))
    unitario: Optional[Decimal] = Field(default=None, sa_type=Numeric(18, 4))
    importe: Optional[Decimal] = Field(default=None, sa_type=Numeric(18, 4))
    condicion: Optional[bool] = None
    warning: bool = False
    error: bool = False
    message: Optional[str] = None


class ReciboConcepto(ReciboConceptoBase, table=True):
    __tablename__ = "recibo_conceptos"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()


class TramoRetroactivoBase(SQLModel):
    liquidacion_id: int = Field(foreign_key="liquidaciones.id", index=True, ondelete="CASCADE")
    beneficiario_id: Optional[int] = Field(default=None, foreign_key="beneficiarios.id")
    fecha_desde: date
    fecha_hasta: date
    haber_mensual: Decimal = _money()
    meses: Decimal = _money()
    importe: Decimal = _money()
    sac: Decimal = _money()
    descripcion: Optional[str] = None


class TramoRetroactivo(TramoRetroactivoBase, table=True):
    __tablename__ = "tramos_retroactivos"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = _created_at()
    updated_at: Optional[datetime] = _updated_at()
