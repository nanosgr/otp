"""Routers CRUD del dominio previsional, registrados en api_router."""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.crud_router import make_crud_router
from app.core.deps import require_permissions
from app.db.database import get_db
from app.services import motor
from app.models import prevision as m


def _liquidacion_abierta(db: Session, obj: Any, action: str) -> None:
    if obj.estado == "CERRADA":
        raise HTTPException(status_code=409, detail="La liquidación está CERRADA y no puede modificarse")


def _padre_liquidacion_abierta(db: Session, obj: Any, action: str) -> None:
    liq = db.get(m.Liquidacion, obj.liquidacion_id)
    if liq is not None and liq.estado == "CERRADA":
        raise HTTPException(status_code=409, detail="La liquidación está CERRADA y no puede modificarse")


def _recibo_concepto_abierto(db: Session, obj: Any, action: str) -> None:
    recibo = db.get(m.Recibo, obj.recibo_id)
    if recibo is not None:
        _padre_liquidacion_abierta(db, recibo, action)


log = logging.getLogger(__name__)

CAMPOS_CONCEPTO = (
    "codigo", "descripcion", "columna", "formula_unidad", "formula_importe", "formula_unitario",
    "formula_condicion", "decimales_unidad", "decimales_importe", "orden", "etapa",
)


def reglas_desde_db(db: Session) -> dict:
    """Arma las reglas del motor con los conceptos activos, las fórmulas auxiliares y los grupos."""
    conceptos = db.exec(select(m.Concepto).where(m.Concepto.is_active == True)).all()  # noqa: E712
    por_id = {c.id: c.codigo for c in conceptos}
    grupos: dict = {}
    for g in db.exec(select(m.GrupoConcepto).where(m.GrupoConcepto.is_active == True)).all():  # noqa: E712
        grupos[g.nombre] = []
    nombres = {g.id: g.nombre for g in db.exec(select(m.GrupoConcepto)).all()}
    for link in db.exec(select(m.ConceptoGrupoLink)).all():
        if link.grupo_id in nombres and nombres[link.grupo_id] in grupos and link.concepto_id in por_id:
            grupos[nombres[link.grupo_id]].append(por_id[link.concepto_id])
    return {
        "conceptos": [{k: getattr(c, k) for k in CAMPOS_CONCEPTO} for c in conceptos],
        "auxiliares": [
            {"codigo": a.codigo, "formato": a.formato, "formula": a.formula}
            for a in db.exec(select(m.FormulaAuxiliar)).all()
        ],
        "grupos": grupos,
    }


def _validar_concepto(db: Session, datos: dict, obj_id: Optional[int]) -> None:
    """Rechaza (422) un concepto con fórmulas inválidas o que cierre un ciclo de dependencias."""
    if not datos.get("is_active", True):
        return
    reglas = reglas_desde_db(db)
    reglas["conceptos"] = [c for c in reglas["conceptos"] if c["codigo"].upper() != datos["codigo"].upper()]
    if obj_id is not None:
        previo = db.get(m.Concepto, obj_id)
        if previo is not None:
            reglas["conceptos"] = [c for c in reglas["conceptos"] if c["codigo"] != previo.codigo]
    reglas["conceptos"].append({k: datos.get(k) for k in CAMPOS_CONCEPTO})
    try:
        problemas = motor.validar_reglas(reglas)
    except motor.MotorNoDisponible:
        log.warning("Motor de fórmulas no disponible: se omite la validación del concepto %s", datos.get("codigo"))
        return
    except motor.FormulaError as exc:
        raise HTTPException(status_code=422, detail=[{"loc": ["formula"], "msg": str(exc)}])
    mios = [p for p in problemas if p["nivel"] == "error" and p["codigo"].upper() == datos["codigo"].upper()]
    if mios:
        raise HTTPException(
            status_code=422,
            detail=[{"loc": [p["campo"] or "formula"], "msg": p["mensaje"]} for p in mios],
        )


# (prefijo URL, recurso de permisos, tabla, base, campos de búsqueda, filtros, guard, validate)
# Campos de solo lectura que se agregan al schema de lectura (no son editables)
READ_EXTRA = {
    m.Liquidacion: {
        "total_credito": (Decimal, Decimal("0")),
        "total_debitos": (Decimal, Decimal("0")),
        "total_liquido": (Decimal, Decimal("0")),
        "calculada_at": (Optional[datetime], None),
    },
}

RESOURCES: List[tuple] = [
    ("causantes", "causantes", m.Causante, m.CausanteBase, ("apellido", "nombre", "dni", "expediente"), ("is_active",), None, None),
    ("beneficiarios", "beneficiarios", m.Beneficiario, m.BeneficiarioBase, ("apellido", "nombre", "dni"), ("causante_id", "parentesco"), None, None),
    ("cargos", "cargos", m.CargoSecuencia, m.CargoSecuenciaBase, (), ("causante_id",), None, None),
    ("servicios", "servicios", m.ServicioPeriodo, m.ServicioPeriodoBase, ("descripcion",), ("causante_id", "tipo"), None, None),
    ("zonas", "zonas", m.ZonaDestino, m.ZonaDestinoBase, ("dependencia",), ("causante_id",), None, None),
    ("conceptos", "conceptos", m.Concepto, m.ConceptoBase, ("codigo", "descripcion"), ("columna", "is_active"), None, _validar_concepto),
    ("grupos-concepto", "grupos_concepto", m.GrupoConcepto, m.GrupoConceptoBase, ("nombre",), (), None, None),
    ("formulas-auxiliares", "formulas_auxiliares", m.FormulaAuxiliar, m.FormulaAuxiliarBase, ("codigo", "descripcion"), (), None, None),
    ("concepto-vigencias", "concepto_vigencias", m.ConceptoVigencia, m.ConceptoVigenciaBase, ("descripcion",), ("concepto_id", "alcance", "tipo_beneficio"), None, None),
    ("tablas", "tablas", m.Tabla, m.TablaBase, ("codigo", "descripcion"), ("is_active",), None, None),
    ("filas", "tablas", m.Fila, m.FilaBase, (), ("tabla_id",), None, None),
    ("parametros", "parametros", m.ParametroHistorial, m.ParametroHistorialBase, ("campo", "descripcion"), ("campo",), None, None),
    ("liquidaciones", "liquidaciones", m.Liquidacion, m.LiquidacionBase, ("periodo", "observaciones"), ("causante_id", "tipo", "estado", "periodo"), _liquidacion_abierta, None),
    ("recibos", "liquidaciones", m.Recibo, m.ReciboBase, (), ("liquidacion_id", "beneficiario_id"), _padre_liquidacion_abierta, None),
    ("recibo-conceptos", "liquidaciones", m.ReciboConcepto, m.ReciboConceptoBase, ("codigo", "descripcion"), ("recibo_id",), _recibo_concepto_abierto, None),
    ("tramos-retroactivos", "liquidaciones", m.TramoRetroactivo, m.TramoRetroactivoBase, (), ("liquidacion_id",), _padre_liquidacion_abierta, None),
]

RECURSOS_DOMINIO = sorted({r[1] for r in RESOURCES})

from app.api.liquidaciones import router as liquidaciones_acciones  # noqa: E402

prevision_router = APIRouter()
prevision_router.include_router(liquidaciones_acciones, prefix="/liquidaciones", tags=["liquidaciones"])
for prefix, resource, table, base, search, filters, guard, validate in RESOURCES:
    prevision_router.include_router(
        make_crud_router(resource=resource, table=table, base=base, search_fields=search,
                         filter_fields=filters, guard=guard, validate=validate,
                         read_extra=READ_EXTRA.get(table)),
        prefix=f"/{prefix}",
        tags=[prefix],
    )


class FormulaIn(BaseModel):
    formula: str


@prevision_router.post("/formulas/validar", tags=["formulas"])
def validar_formula(
    body: FormulaIn,
    db: Session = Depends(get_db),
    _=Depends(require_permissions(["conceptos:read"])),
):
    """Valida la sintaxis de una fórmula (con las auxiliares vigentes) y devuelve lo que referencia."""
    auxiliares = reglas_desde_db(db)["auxiliares"]
    try:
        return motor.validar_formula(body.formula, auxiliares)
    except motor.MotorNoDisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except motor.FormulaError as exc:
        raise HTTPException(status_code=422, detail=[{"loc": ["formula"], "msg": str(exc)}])
