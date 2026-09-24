"""Carga las reglas de la base una sola vez por liquidación y las resuelve a una fecha para el motor."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from sqlmodel import Session, select

from app.models import prevision as m

CAMPOS_CONCEPTO = (
    "codigo", "descripcion", "columna", "formula_unidad", "formula_importe", "formula_unitario",
    "formula_condicion", "decimales_unidad", "decimales_importe", "orden",
)


class SinReglas(Exception):
    """No hay conceptos vigentes para la fecha pedida."""


def _vigente(desde: Optional[date], hasta: Optional[date], fecha: date) -> bool:
    return (desde is None or desde <= fecha) and (hasta is None or hasta >= fecha)


def _tipado(valor: str, tipo: str) -> Any:
    if tipo == "decimal" or tipo == "int":
        return {"decimal": valor}
    if tipo == "date":
        return {"date": valor}
    if tipo == "bool":
        return valor.strip().lower() in ("1", "true", "si", "sí")
    return valor


class ReglasDB:
    """Instantánea en memoria de conceptos, vigencias, tablas, parámetros y auxiliares."""

    def __init__(self, db: Session):
        self.conceptos: Dict[int, m.Concepto] = {c.id: c for c in db.exec(select(m.Concepto).where(m.Concepto.is_active == True)).all()}  # noqa: E712
        self.vigencias: Dict[int, List[m.ConceptoVigencia]] = defaultdict(list)
        for v in db.exec(select(m.ConceptoVigencia)).all():
            self.vigencias[v.concepto_id].append(v)
        filas: Dict[int, List[m.Fila]] = defaultdict(list)
        for f in db.exec(select(m.Fila).order_by(m.Fila.tabla_id, m.Fila.orden, m.Fila.id)).all():
            filas[f.tabla_id].append(f)
        self.tablas: Dict[str, List[tuple]] = defaultdict(list)
        for t in db.exec(select(m.Tabla).where(m.Tabla.is_active == True)).all():  # noqa: E712
            self.tablas[t.codigo.upper()].append((t, filas[t.id]))
        self.parametros: Dict[str, List[m.ParametroHistorial]] = defaultdict(list)
        for p in db.exec(select(m.ParametroHistorial)).all():
            self.parametros[p.campo.upper()].append(p)
        self.auxiliares = [
            {"codigo": a.codigo, "formato": a.formato, "formula": a.formula}
            for a in db.exec(select(m.FormulaAuxiliar).order_by(m.FormulaAuxiliar.orden)).all()
        ]
        nombres = {g.id: g.nombre for g in db.exec(select(m.GrupoConcepto).where(m.GrupoConcepto.is_active == True)).all()}  # noqa: E712
        codigos = {c.id: c.codigo for c in self.conceptos.values()}
        self.grupos: Dict[str, List[str]] = {n: [] for n in nombres.values()}
        for link in db.exec(select(m.ConceptoGrupoLink)).all():
            if link.grupo_id in nombres and link.concepto_id in codigos:
                self.grupos[nombres[link.grupo_id]].append(codigos[link.concepto_id])

    # ------------------------------------------------------------------ cortes

    def cortes(self, desde: date, hasta: date) -> Set[date]:
        """Fechas en que cambia alguna regla (inicio de vigencia o día siguiente al fin) dentro de (desde, hasta]."""
        fechas: Set[date] = set()

        def agregar(vd: Optional[date], vh: Optional[date]) -> None:
            if vd:
                fechas.add(vd)
            if vh:
                fechas.add(vh + timedelta(days=1))

        for lista in self.vigencias.values():
            for v in lista:
                agregar(v.vigencia_desde, v.vigencia_hasta)
        for versiones in self.tablas.values():
            for t, _ in versiones:
                agregar(t.vigencia_desde, t.vigencia_hasta)
        for lista in self.parametros.values():
            for p in lista:
                agregar(p.vigencia_desde, p.vigencia_hasta)
        return {f for f in fechas if desde < f <= hasta}

    # ------------------------------------------------------------------ a una fecha

    def reglas_a(self, fecha: date, tipo_beneficio: str, etapa: str) -> Dict[str, Any]:
        conceptos = []
        for cid, c in self.conceptos.items():
            if c.etapa != etapa:
                continue
            aplicables = [
                v for v in self.vigencias.get(cid, [])
                if _vigente(v.vigencia_desde, v.vigencia_hasta, fecha)
                and (v.alcance == "general" or (v.alcance == "tipo_beneficio" and v.tipo_beneficio == tipo_beneficio))
            ]
            if not aplicables:
                continue
            v = max(aplicables, key=lambda x: x.vigencia_desde or date.min)
            d = {k: getattr(c, k) for k in CAMPOS_CONCEPTO}
            if v.orden is not None:
                d["orden"] = v.orden
            conceptos.append(d)
        if not conceptos:
            raise SinReglas(f"No hay reglas vigentes al {fecha.isoformat()} para {tipo_beneficio} (etapa {etapa})")
        return {"conceptos": conceptos, "auxiliares": self.auxiliares, "grupos": self.grupos}

    def tablas_a(self, fecha: date) -> Dict[str, Any]:
        out = {}
        for codigo, versiones in self.tablas.items():
            vigentes = [(t, f) for t, f in versiones if _vigente(t.vigencia_desde, t.vigencia_hasta, fecha)]
            if not vigentes:
                continue
            t, filas = max(vigentes, key=lambda x: x[0].vigencia_desde or date.min)
            out[codigo] = {"columnas": t.columnas, "filas": [f.valores for f in filas]}
        return out

    def historial_a(self, fecha: date) -> Dict[str, Any]:
        out = {}
        for campo, lista in self.parametros.items():
            items = [
                {"desde": p.vigencia_desde, "hasta": p.vigencia_hasta, "valor": _tipado(p.valor, p.tipo_dato)}
                for p in lista if _vigente(p.vigencia_desde, p.vigencia_hasta, fecha)
            ]
            if items:
                out[campo] = items
        return out

    def contexto_a(self, fecha: date, variables: Dict[str, Any], beneficiarios: Optional[list] = None) -> Dict[str, Any]:
        return {
            "fecha": fecha,
            "variables": variables,
            "tablas": self.tablas_a(fecha),
            "historial": self.historial_a(fecha),
            "beneficiarios": beneficiarios or [],
        }


def variables_de_cargo(causante: m.Causante, cargo: m.CargoSecuencia, beneficiario: Optional[m.Beneficiario]) -> Dict[str, Any]:
    """Variables del contexto a partir de la hoja DATOS (causante, cargo y, en pensiones, beneficiario)."""
    dec = lambda x: Decimal(str(x if x is not None else 0))
    return {
        "TIPO_PERSONAL": causante.tipo_personal,
        "CLASE": cargo.clase,
        "RESP_JERARQUICA_PORC": dec(cargo.responsabilidad_jerarquica_porcentaje),
        "RECARGO_SERVICIO_PORC": dec(cargo.recargo_servicio_porcentaje),
        "TITULO": cargo.titulo,
        "NIVEL_PREGRADO": cargo.titulo_pregrado_nivel,
        "RIESGO_ESPECIAL": bool(cargo.riesgo_especial),
        "ZONA_PORC": dec(cargo.zona_porcentaje),
        "ZONA_CLASE": cargo.zona_clase,
        "ANIOS_ANTIGUEDAD": dec(cargo.anios_antiguedad),
        "CUERPO_APOYO_PORC": dec(cargo.cuerpo_apoyo_porcentaje),
        "ADICIONAL_SEGURIDAD": bool(cargo.adicional_seguridad),
        "PORCENTAJE_RETIRO_MANUAL": dec(cargo.porcentaje_retiro),
        "PORCENTAJE": dec(beneficiario.porcentaje) if beneficiario else Decimal(100),
        "ART37": bool(beneficiario.art37) if beneficiario else False,
        "PARENTESCO": beneficiario.parentesco if beneficiario else "titular",
    }
