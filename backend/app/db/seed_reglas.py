"""Semilla de reglas de liquidación (retiros y pensiones policiales) desde las planillas de la oficina.

Los datos por vigencia (escala de clase, porcentajes, montos fijos, qué conceptos existen cada mes) se extraen de
la planilla con `scripts/import_reglas_planillas.py` a `seed_data/reglas_planillas.json` (mayo 2022 en adelante).
Las fórmulas se escriben acá, una sola por concepto para todas las vigencias: un concepto que no existe en una
fecha (sin vigencia) vale 0 en las referencias `#codigo`, lo que reproduce los cambios de estructura de las hojas.

Uso:  python -m app.db.seed_reglas [--force]
Sin --force no toca lo que ya existe (respeta ediciones manuales); con --force lo reemplaza.
"""
import json
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from sqlmodel import Session, select

from app.db.database import engine
from app.models.prevision import (
    Concepto, ConceptoVigencia, FormulaAuxiliar, Fila, ParametroHistorial, Tabla,
)

DATA = Path(__file__).parent / "seed_data" / "reglas_planillas.json"
DESDE = date(2022, 5, 1)

BASE = "#10 + #23 + #58 + #24 + #31 + #59 + #83 + #80"
HAB = 10  # decimales de importe de los conceptos del haber (la planilla no redondea los pasos intermedios)

# codigo: (columna, orden, formula_importe)
HABER: Dict[str, tuple] = {
    "10": ("REMUNERATIVO", 10, "TABLA('ESCALA_CLASE', COL.CLASE = CLASE, COL.HABER)"),
    "23": ("REMUNERATIVO", 23, "HISTORIAL('BASE_JEFE') * RESP_JERARQUICA_PORC%"),
    "58": ("REMUNERATIVO", 58, "HISTORIAL('BASE_JEFE') * RECARGO_SERVICIO_PORC%"),
    "24": ("REMUNERATIVO", 24, "HISTORIAL('BASE_JEFE') * IF(TITULO = 'grado', HISTORIAL('PORC_TITULO_GRADO'), "
                               "IF(TITULO = 'posgrado', HISTORIAL('PORC_TITULO_POSGRADO'), 0))%"),
    "31": ("REMUNERATIVO", 31, "HISTORIAL('BASE_PREGRADO') * IF(TITULO = 'grado' OR TITULO = 'posgrado', 0, "
                               "TABLA('PORC_TITULO_PREGRADO', COL.NIVEL <= NIVEL_PREGRADO, COL.PORC, 0))%"),
    "59": ("REMUNERATIVO", 59, "HISTORIAL('BASE_JEFE') * IF(RIESGO_ESPECIAL, HISTORIAL('PORC_RIESGO_ESPECIAL'), 0)%"),
    "83": ("REMUNERATIVO", 83, "TABLA('ESCALA_CLASE', COL.CLASE = ZONA_CLASE, COL.HABER, 0) * ZONA_PORC%"),
    "80": ("REMUNERATIVO", 80, "#10 * HISTORIAL('PORC_ANTIGUEDAD')% * ANIOS_ANTIGUEDAD"),
    "90": ("REMUNERATIVO", 90, f"({BASE} + #66) * HISTORIAL('PORC_ADIC_FZA_SEG')%"),
    "64": ("REMUNERATIVO", 64, "HISTORIAL('MONTO_64')"),
    "91": ("REMUNERATIVO", 91, f"({BASE} + #90 + #64) * HISTORIAL('PORC_AUM_0705')%"),
    "95": ("REMUNERATIVO", 95, f"({BASE} + #90 + #64 + #91) * CUERPO_APOYO_PORC%"),
    "92": ("REMUNERATIVO", 92, f"({BASE} + #90 + #64 + #91 + #95) * HISTORIAL('PORC_AUM_0907')%"),
    "93": ("REMUNERATIVO", 93, f"({BASE} + #90 + #64 + #91 + #95 + #92) * HISTORIAL('PORC_AUM_0308')%"),
    "50": ("REMUNERATIVO", 50, "HISTORIAL('MONTO_50')"),
    "51": ("REMUNERATIVO", 51, "HISTORIAL('BASE_JEFE') * HISTORIAL('PORC_PERS_SEG_2022')%"),
    "52": ("REMUNERATIVO", 52, "#10 * HISTORIAL('PORC_FORTALECIMIENTO')%"),
    "65": ("REMUNERATIVO", 65, "IF(ADICIONAL_SEGURIDAD, HISTORIAL('MONTO_65'), 0)"),
    "66": ("REMUNERATIVO", 66, "HISTORIAL('MONTO_66')"),
    "73": ("REMUNERATIVO", 73, "HISTORIAL('MONTO_73')"),
    "74": ("REMUNERATIVO", 74, "#73"),
    "75": ("REMUNERATIVO", 75, "HISTORIAL('MONTO_75')"),
}

PORC_RETIRO = ("IF(PORCENTAJE_RETIRO_MANUAL > 0, PORCENTAJE_RETIRO_MANUAL, "
               "IF(TIPO_PERSONAL = 'superior', "
               "TABLA('RETIRO_SUPERIOR', COL.ANIOS <= ANIOS_ANTIGUEDAD, COL.PORC, 0), "
               "TABLA('RETIRO_SUBALTERNO', COL.ANIOS <= ANIOS_ANTIGUEDAD, COL.PORC, 0)))")

# codigo: (descripcion, columna, etapa, orden, formula_importe, decimales, tipo_beneficio)
# HABER_PONDERADO = suma de (total remunerativo de cada cargo x % de su secuencia); lo calcula el liquidador.
DERIVADOS: Dict[str, tuple] = {
    "HABER_RETIRO": ("Haber de retiro", "AUXILIAR", "beneficio", 1000, f"HABER_PONDERADO * ({PORC_RETIRO})%", HAB, None),
    "PENSION_TOTAL": ("Pensión (75% del haber de retiro)", "AUXILIAR", "beneficio", 1010,
                      "#HABER_RETIRO * HISTORIAL('PORC_PENSION')%", HAB, "pension"),
    "PENSION_BENEFICIARIO": ("Pensión del beneficiario", "AUXILIAR", "beneficio", 1020,
                             "#PENSION_TOTAL * PORCENTAJE / 100", HAB, "pension"),
    "ART37": ("Art. 37 (5% del haber de retiro)", "AUXILIAR", "beneficio", 1030,
              "IF(ART37, #HABER_RETIRO * HISTORIAL('PORC_ART37')%, 0)", HAB, "pension"),
    "CREDITO_RETROACTIVO": ("Crédito (haberes y SAC)", "REMUNERATIVO", "liquidacion", 2000, "SUBTOTAL_CREDITO", 2, None),
    "DESC_LEY_FEDERAL": ("Descuento Ley Federal", "DESCUENTO", "liquidacion", 2010,
                         "SUBTOTAL_CREDITO * HISTORIAL('PORC_LEY_FEDERAL')%", 2, "retiro"),
    "DESC_OSEP_CUOTA": ("Cuota OSEP", "DESCUENTO", "liquidacion", 2020,
                        "SUBTOTAL_CREDITO * HISTORIAL('PORC_OSEP_CUOTA')%", 2, None),
    "DESC_OSEP_DIRECTO": ("OSEP directo", "DESCUENTO", "liquidacion", 2030,
                          "SUBTOTAL_CREDITO * HISTORIAL('PORC_OSEP_DIRECTO')%", 2, None),
    "DESC_OSEP_INCAPACIDAD": ("OSEP incapacidad", "DESCUENTO", "liquidacion", 2040,
                              "SUBTOTAL_CREDITO * HISTORIAL('PORC_OSEP_INCAPACIDAD')%", 2, None),
    "ANTICIPO": ("Anticipo percibido", "DESCUENTO", "liquidacion", 2050, "ANTICIPO_IMPORTE", 2, None),
}

# Parámetros con vigencia que la planilla trae escritos en rótulos/celdas fijas (no en los bloques mensuales)
PARAMETROS_FIJOS = {
    "PORC_TITULO_GRADO": 20, "PORC_TITULO_POSGRADO": 25,   # DATOS: "T Grado 20% - Posgrado 25%" (desde mayo 2022)
    "PORC_PENSION": 75, "PORC_ART37": 5,                     # hojas de período (D46) y DATOS (C15)
    "PORC_LEY_FEDERAL": 8, "PORC_OSEP_CUOTA": 5, "PORC_OSEP_DIRECTO": 0.25, "PORC_OSEP_INCAPACIDAD": 0.75,  # Planilla Retiro
}

# % de pregrado según nivel (LOOKUP {0,1,2} -> {0,5%,10%}); en orden descendente para emular LOOKUP con "<="
PREGRADO = [[2, "10"], [1, "5"], [0, "0"]]


def _d(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def _crear_tabla(db: Session, codigo: str, descripcion: str, columnas: list, filas: list,
                 desde: Optional[date], hasta: Optional[date], force: bool) -> None:
    existente = db.exec(select(Tabla).where(Tabla.codigo == codigo, Tabla.vigencia_desde == desde)).first()
    if existente and not force:
        return
    if existente:
        for f in db.exec(select(Fila).where(Fila.tabla_id == existente.id)).all():
            db.delete(f)
        db.delete(existente)
        db.flush()
    t = Tabla(codigo=codigo, descripcion=descripcion, columnas=columnas, vigencia_desde=desde, vigencia_hasta=hasta)
    db.add(t)
    db.flush()
    for i, valores in enumerate(filas):
        db.add(Fila(tabla_id=t.id, orden=i, valores=valores))


def _param(db: Session, campo: str, valor, desde: Optional[date], hasta: Optional[date], descripcion: str, force: bool) -> None:
    existente = db.exec(select(ParametroHistorial).where(
        ParametroHistorial.campo == campo, ParametroHistorial.vigencia_desde == desde)).first()
    if existente and not force:
        return
    if existente:
        db.delete(existente)
        db.flush()
    db.add(ParametroHistorial(campo=campo, valor=str(valor), tipo_dato="decimal",
                              vigencia_desde=desde, vigencia_hasta=hasta, descripcion=descripcion))


def _concepto(db: Session, codigo: str, force: bool, **campos) -> Concepto:
    c = db.exec(select(Concepto).where(Concepto.codigo == codigo)).first()
    if c is None:
        c = Concepto(codigo=codigo, **campos)
        db.add(c)
    elif force:
        for k, v in campos.items():
            setattr(c, k, v)
        db.add(c)
    db.flush()
    return c


def _vigencias(db: Session, concepto: Concepto, rangos: List[dict], tipo_beneficio: Optional[str], force: bool) -> None:
    previas = db.exec(select(ConceptoVigencia).where(ConceptoVigencia.concepto_id == concepto.id)).all()
    if previas and not force:
        return
    for v in previas:
        db.delete(v)
    db.flush()
    for r in rangos:
        db.add(ConceptoVigencia(
            concepto_id=concepto.id,
            alcance="tipo_beneficio" if tipo_beneficio else "general",
            tipo_beneficio=tipo_beneficio,
            vigencia_desde=_d(r["desde"]), vigencia_hasta=_d(r["hasta"]),
        ))


def seed_reglas(db: Session, force: bool = False) -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    nombres = data["nombres"]

    # Tablas
    for e in data["escalas"]:
        filas = [[int(k), str(v)] for k, v in e["clases"].items()]
        _crear_tabla(db, "ESCALA_CLASE", "Haber mensual por clase",
                     [{"nombre": "CLASE", "tipo": "int"}, {"nombre": "HABER", "tipo": "decimal"}],
                     filas, _d(e["desde"]), _d(e["hasta"]), force)
    cols_retiro = [{"nombre": "ANIOS", "tipo": "int"}, {"nombre": "PORC", "tipo": "decimal"}]
    # Asignación inferida (confirmar con la oficina): 25 años -> subalterno, 30 años -> superior
    _crear_tabla(db, "RETIRO_SUBALTERNO", "% de retiro por años de servicio (100% a los 25 años)", cols_retiro,
                 [[a, str(p)] for a, p in reversed(data["retiro_por_anios"]["K"])], None, None, force)
    _crear_tabla(db, "RETIRO_SUPERIOR", "% de retiro por años de servicio (100% a los 30 años)", cols_retiro,
                 [[a, str(p)] for a, p in reversed(data["retiro_por_anios"]["N"])], None, None, force)
    _crear_tabla(db, "PORC_TITULO_PREGRADO", "% por título de pregrado según nivel",
                 [{"nombre": "NIVEL", "tipo": "int"}, {"nombre": "PORC", "tipo": "decimal"}],
                 PREGRADO, DESDE, None, force)

    # Parámetros con vigencia
    for campo, serie in data["parametros"].items():
        for r in serie:
            _param(db, campo, r["valor"], _d(r["desde"]), _d(r["hasta"]), f"Planilla {data['fuente']}", force)
    for campo, valor in PARAMETROS_FIJOS.items():
        _param(db, campo, valor, DESDE, None, "Rótulos/celdas fijas de la planilla", force)

    # Conceptos del haber, con las vigencias en que existen en la planilla
    for codigo, (columna, orden, formula) in HABER.items():
        c = _concepto(db, codigo, force, descripcion=nombres.get(codigo, codigo), columna=columna, etapa="haber",
                      formula_importe=formula, decimales_importe=HAB, orden=orden)
        _vigencias(db, c, data["presencia"][codigo], None, force)

    # Conceptos derivados (retiro, pensión, descuentos de la liquidación)
    for codigo, (desc, columna, etapa, orden, formula, dec, tipo) in DERIVADOS.items():
        c = _concepto(db, codigo, force, descripcion=desc, columna=columna, etapa=etapa,
                      formula_importe=formula, decimales_importe=dec, orden=orden)
        _vigencias(db, c, [{"desde": DESDE.isoformat(), "hasta": None}], tipo, force)

    db.commit()
    return {"vigencias": data["cobertura"]["vigencias"], "desde": data["cobertura"]["desde"]}


if __name__ == "__main__":
    with Session(engine) as session:
        info = seed_reglas(session, force="--force" in sys.argv)
    print(f"Reglas cargadas: {info['vigencias']} vigencias desde {info['desde']}")
