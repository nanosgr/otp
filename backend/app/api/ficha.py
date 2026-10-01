"""Ficha del causante para la liquidación proyectada: puntos 1-4 y anexo de zona calculados en vivo."""
from datetime import date
from decimal import Decimal
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.deps import require_permissions
from app.db.database import get_db
from app.models import prevision as m
from app.services.computo import computo
from app.services.zona import calcular_zona

router = APIRouter()


def _json(o: Any) -> Any:
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    return o


@router.get("/{causante_id}/ficha")
def ficha(causante_id: int, db: Session = Depends(get_db), _=Depends(require_permissions(["causantes:read"]))) -> Dict[str, Any]:
    causante = db.get(m.Causante, causante_id)
    if causante is None:
        raise HTTPException(status_code=404, detail="Causante no encontrado")
    filas = db.exec(select(m.ComputoServicio).where(m.ComputoServicio.causante_id == causante_id)
                    .order_by(m.ComputoServicio.orden, m.ComputoServicio.id)).all()
    cargos = db.exec(select(m.CargoSecuencia).where(m.CargoSecuencia.causante_id == causante_id)
                     .order_by(m.CargoSecuencia.secuencia)).all()
    destinos = db.exec(select(m.ZonaDestino).where(m.ZonaDestino.causante_id == causante_id)
                       .order_by(m.ZonaDestino.fecha_desde)).all()
    liqs = db.exec(select(m.Liquidacion).where(m.Liquidacion.causante_id == causante_id).order_by(m.Liquidacion.id)).all()
    out_cargos = []
    for c in cargos:
        items = db.exec(select(m.EncasillamientoItem).where(m.EncasillamientoItem.cargo_id == c.id)
                        .order_by(m.EncasillamientoItem.orden, m.EncasillamientoItem.id)).all()
        out_cargos.append({**c.model_dump(), "encasillamiento": [i.model_dump() for i in items]})
    return _json({
        "causante": causante.model_dump(),
        "computo": {"filas": [f.model_dump() for f in filas], "totales": computo(filas)},
        "cargos": out_cargos,
        "zonas": [z.model_dump() for z in destinos],
        "zona": calcular_zona(destinos, causante.tipo_personal, causante.fecha_renuncia_condicionada),
        "liquidaciones": [{"id": l.id, "periodo": l.periodo, "tipo": l.tipo, "modalidad": l.modalidad, "estado": l.estado,
                           "total_liquido": l.total_liquido, "calculada_at": l.calculada_at} for l in liqs],
    })
