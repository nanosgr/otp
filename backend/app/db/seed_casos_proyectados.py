"""Carga los 10 casos de liquidación proyectada (renuncia/baja condicionada) relevados de la oficina.

Por caso: causante (1. datos del expediente), cómputo de servicios (2.), cargo con imputación (3.) y encasillamiento
(4.), destinos de zona (anexo) y una liquidación `proyectada` ABIERTA del mes base, que se calcula al cargarla.
Los datos salen de `seed_data/casos_proyectados.json` (`scripts/import_casos_proyectados.py`).

Uso:  python -m app.db.seed_casos_proyectados [--force]
Sin --force saltea los causantes que ya existen (por DNI); con --force los borra y los vuelve a crear.
Requiere las reglas: python -m app.db.seed_reglas
"""
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from sqlmodel import Session, delete, select

import app.models.models  # noqa: F401  (registra users para las FK de liquidaciones)
from app.db.database import engine
from app.models import prevision as m
from app.services.liquidador import calcular_liquidacion

DATA = Path(__file__).parent / "seed_data" / "casos_proyectados.json"


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def _dec(x) -> Optional[Decimal]:
    return None if x is None else Decimal(str(x))


def _borrar(db: Session, causante: m.Causante) -> None:
    liqs = select(m.Liquidacion.id).where(m.Liquidacion.causante_id == causante.id)
    recibos = select(m.Recibo.id).where(m.Recibo.liquidacion_id.in_(liqs))
    cargos = select(m.CargoSecuencia.id).where(m.CargoSecuencia.causante_id == causante.id)
    for stmt in (
        delete(m.ReciboConcepto).where(m.ReciboConcepto.recibo_id.in_(recibos)),
        delete(m.Recibo).where(m.Recibo.liquidacion_id.in_(liqs)),
        delete(m.TramoRetroactivo).where(m.TramoRetroactivo.liquidacion_id.in_(liqs)),
        delete(m.Liquidacion).where(m.Liquidacion.causante_id == causante.id),
        delete(m.EncasillamientoItem).where(m.EncasillamientoItem.cargo_id.in_(cargos)),
        *(delete(t).where(t.causante_id == causante.id) for t in (
            m.CargoSecuencia, m.ComputoServicio, m.ZonaDestino, m.ServicioPeriodo, m.Beneficiario)),
        delete(m.Causante).where(m.Causante.id == causante.id),
    ):
        db.exec(stmt)
    db.commit()


def cargar_caso(db: Session, caso: dict, calcular: bool = True) -> m.Liquidacion:
    datos = dict(caso["causante"])
    for k in ("fecha_ingreso", "fecha_renuncia_condicionada", "cuadro_servicio_desde", "cuadro_servicio_hasta"):
        datos[k] = _d(datos.get(k))
    causante = m.Causante(**datos)
    db.add(causante)
    db.commit()
    db.refresh(causante)
    for i, f in enumerate(caso["computo"]):
        db.add(m.ComputoServicio(causante_id=causante.id, orden=i, **f))
    cargo_d = dict(caso["cargo"])
    for k in ("porcentaje_secuencia", "anios_antiguedad", "zona_porcentaje"):
        cargo_d[k] = _dec(cargo_d[k])
    cargo = m.CargoSecuencia(causante_id=causante.id, **cargo_d)
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    for it in caso["encasillamiento"]:
        db.add(m.EncasillamientoItem(cargo_id=cargo.id, codigo=it["codigo"], descripcion=it["descripcion"],
                                     valor=_dec(it["valor"]), aplica=it["aplica"], orden=it["orden"]))
    for z in caso["zonas"]:
        db.add(m.ZonaDestino(causante_id=causante.id, dependencia=z["dependencia"], porcentaje_zona=_dec(z["porcentaje_zona"]),
                             fecha_desde=_d(z["fecha_desde"]), fecha_hasta=_d(z["fecha_hasta"])))
    liq = m.Liquidacion(causante_id=causante.id, periodo=caso["periodo"], tipo="retiro", modalidad="proyectada",
                        asunto=caso["asunto"],
                        observaciones=f"Caso relevado: hoja {caso['hoja']}. " + " ".join(caso.get("notas") or []))
    db.add(liq)
    db.commit()
    db.refresh(liq)
    if calcular:
        calcular_liquidacion(db, liq.id)
    return liq


def seed_casos(db: Session, force: bool = False) -> List[str]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cargados = []
    for caso in data["casos"]:
        previo = db.exec(select(m.Causante).where(m.Causante.dni == caso["causante"]["dni"])).first()
        if previo is not None:
            if not force:
                continue
            _borrar(db, previo)
        cargar_caso(db, caso)
        cargados.append(caso["hoja"])
    return cargados


if __name__ == "__main__":
    with Session(engine) as session:
        hojas = seed_casos(session, force="--force" in sys.argv)
    print(f"Casos cargados: {len(hojas)}" + (f" ({', '.join(hojas)})" if hojas else " (ya existían; usar --force)"))
