"""Arma el resumen de una liquidación calculada (equivalente a la 'Planilla de resumen de liquidación')."""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import prevision as m


def _f(x: Any) -> str:
    return "0" if x is None else str(Decimal(str(x)))


def armar_resumen(db: Session, liquidacion_id: int) -> Dict[str, Any]:
    liq = db.get(m.Liquidacion, liquidacion_id)
    if liq is None:
        raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    causante = db.get(m.Causante, liq.causante_id)
    recibos = db.exec(select(m.Recibo).where(m.Recibo.liquidacion_id == liq.id).order_by(m.Recibo.numero)).all()
    tramos = db.exec(select(m.TramoRetroactivo).where(m.TramoRetroactivo.liquidacion_id == liq.id)
                     .order_by(m.TramoRetroactivo.fecha_desde, m.TramoRetroactivo.sac, m.TramoRetroactivo.id)).all()
    out_recibos: List[Dict[str, Any]] = []
    for r in recibos:
        conceptos = db.exec(select(m.ReciboConcepto).where(m.ReciboConcepto.recibo_id == r.id)
                            .order_by(m.ReciboConcepto.id)).all()
        snap = r.snapshot or {}
        propios = [t for t in tramos if t.beneficiario_id == r.beneficiario_id]
        liquidacion_final = [c for c in conceptos if c.codigo in _CODIGOS_LIQUIDACION]
        descuentos = [c for c in liquidacion_final if c.columna == "DESCUENTO"]
        out_recibos.append({
            "numero": r.numero,
            "beneficiario": snap.get("beneficiario"),
            "rango": snap.get("rango"),
            "haber_mensual_actual": snap.get("haber_mensual_actual"),
            "tramos": [{
                "desde": t.fecha_desde.isoformat(), "hasta": t.fecha_hasta.isoformat(), "descripcion": t.descripcion,
                "haber_mensual": _f(t.haber_mensual), "meses": _f(t.meses), "importe": _f(t.importe), "es_sac": bool(t.sac),
            } for t in propios],
            "credito": _f(r.sueldo_bruto),
            "descuentos": [{"codigo": c.codigo, "descripcion": c.descripcion, "importe": _f(c.importe)} for c in descuentos],
            "total_descuentos": _f(r.total_descuento),
            "liquido": _f(r.sueldo_neto),
            "haber_ponderado": snap.get("haber_ponderado_actual"),
            "cargos": [{"secuencia": t["secuencia"], "porcentaje": _f(t["porcentaje"]), "total": _f(t["total"])}
                       for t in snap.get("totales_cargos_actual", [])],
            "conceptos_haber": [{"codigo": c.codigo, "descripcion": c.descripcion, "columna": c.columna, "secuencia": c.secuencia,
                                 "unidad": None if c.unidad is None else _f(c.unidad),
                                 "unitario": None if c.unitario is None else _f(c.unitario), "importe": _f(c.importe)}
                                for c in conceptos if c.codigo not in _CODIGOS_LIQUIDACION],
        })
        if liq.modalidad == "proyectada":
            out_recibos[-1]["proyectada"] = _proyectada(snap, conceptos)
    return {
        "liquidacion": {
            "id": liq.id, "periodo": liq.periodo, "tipo": liq.tipo, "estado": liq.estado,
            "modalidad": liq.modalidad, "asunto": liq.asunto,
            "fecha_desde": liq.fecha_desde.isoformat() if liq.fecha_desde else None,
            "fecha_hasta": liq.fecha_hasta.isoformat() if liq.fecha_hasta else None,
            "fecha_pago": liq.fecha_pago.isoformat() if liq.fecha_pago else None,
            "anticipo_importe": _f(liq.anticipo_importe),
            "total_credito": _f(liq.total_credito), "total_debitos": _f(liq.total_debitos), "total_liquido": _f(liq.total_liquido),
            "calculada_at": liq.calculada_at.isoformat() if liq.calculada_at else None,
            "observaciones": liq.observaciones,
        },
        "causante": {"id": causante.id, **{k: (v.isoformat() if hasattr(v, "isoformat") else v)
                                           for k, v in ((k, getattr(causante, k)) for k in m.CausanteBase.model_fields)}},
        "recibos": out_recibos,
    }


# conceptos de la etapa "liquidación" (se muestran aparte del detalle del haber)
_CODIGOS_LIQUIDACION = {
    "CREDITO_RETROACTIVO", "DESC_LEY_FEDERAL", "DESC_OSEP_CUOTA", "DESC_OSEP_DIRECTO", "DESC_OSEP_INCAPACIDAD", "ANTICIPO",
}


def _proyectada(snap: Dict[str, Any], conceptos: List[m.ReciboConcepto]) -> Dict[str, Any]:
    """Puntos 1-5 y anexo de zona de la liquidación proyectada (a partir del snapshot del recibo)."""
    retiro = next((c for c in conceptos if c.codigo == "HABER_RETIRO"), None)
    cargos = snap.get("cargos") or []
    return {
        "computo": snap.get("computo"),
        "imputacion": cargos[0] if cargos else None,
        "encasillamiento": (snap.get("encasillamiento") or {}).get(str(cargos[0]["secuencia"])) if cargos else [],
        "zona": snap.get("zona"),
        "porcentaje_retiro": None if retiro is None or retiro.unidad is None else _f(retiro.unidad),
        "total_haberes": None if retiro is None or retiro.unitario is None else _f(retiro.unitario),
        "haber_retiro": None if retiro is None else _f(retiro.importe),
    }
