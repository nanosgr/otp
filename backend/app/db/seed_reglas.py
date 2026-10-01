"""Semilla de reglas de liquidación (retiros y pensiones policiales) desde las planillas de la oficina.

Los datos por vigencia (escala de clase, porcentajes, montos fijos, qué conceptos existen cada mes) se extraen de
la planilla con `scripts/import_reglas_planillas.py` a `seed_data/reglas_planillas.json` (mayo 2022 en adelante).
Las fórmulas se escriben acá, una sola por concepto para todas las vigencias: un concepto que no existe en una
fecha (sin vigencia) vale 0 en las referencias `#codigo`, lo que reproduce los cambios de estructura de las hojas.

Cada concepto del haber tiene unidad (% o cantidad), unitario (base) e importe, como la planilla de liquidación
proyectada. La unidad sale del encasillamiento del cargo (`CAMPO_UNIDAD`) cuando lo hay y, si no, de los campos del
cargo / parámetros (planilla de retroactivos). Con encasillamiento, un concepto se liquida solo si está encasillado
(`CAMPO_PRESENTE`); sin encasillamiento (`ENCASILLADO` falso) se liquidan todos los vigentes, como antes.

Juego penitenciario (`escalafon='penitenciario'`) y vigencias que la planilla de retroactivos no cubre: se cargan desde
`seed_data/reglas_proyectadas.json` (escalas PARCIALES deducidas de las liquidaciones proyectadas relevadas, ver
`scripts/import_casos_proyectados.py`).

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
DATA_PROYECTADAS = Path(__file__).parent / "seed_data" / "reglas_proyectadas.json"
DESDE = date(2022, 5, 1)
DESDE_PEN = date(2022, 4, 1)

BASE = "#10 + #23 + #58 + #24 + #31 + #59 + #83 + #80"
BASE_PEN = "#10 + #26 + #23 + #27 + #58 + #24 + #31 + #83 + #80"
HAB = 10  # decimales de importe de los conceptos del haber (la planilla no redondea los pasos intermedios)

# Condición: con encasillamiento solo se liquida lo encasillado; sin él, todo lo vigente
ENCASILLADO = "NOT ENCASILLADO OR CAMPO_PRESENTE"


def enc(defecto: str) -> str:
    """Unidad: el valor del encasillamiento si está encasillado; si no, el dato del cargo o el parámetro."""
    return f"IF(CAMPO_PRESENTE, CAMPO_UNIDAD, {defecto})"


def enc_param(param: str) -> str:
    """Unidad de un % general: el del encasillamiento si trae valor ("$" = el vigente), si no el parámetro."""
    return f"IF(CAMPO_PRESENTE AND CAMPO_UNIDAD > 0, CAMPO_UNIDAD, HISTORIAL('{param}'))"


# codigo: (orden, formula_unidad, formula_unitario, formula_importe, formula_condicion)
# El importe se escribe completo (no UNITARIO x UNIDAD) para no redondear la base a 4 decimales.
HABER: Dict[str, tuple] = {
    "10": (10, "CLASE", None, "TABLA('ESCALA_CLASE', COL.CLASE = CLASE, COL.HABER)", None),
    "23": (23, enc("RESP_JERARQUICA_PORC"), "HISTORIAL('BASE_JEFE')", "HISTORIAL('BASE_JEFE') * UNIDAD%", ENCASILLADO),
    "58": (58, enc("RECARGO_SERVICIO_PORC"), "HISTORIAL('BASE_JEFE')", "HISTORIAL('BASE_JEFE') * UNIDAD%", ENCASILLADO),
    "24": (24, enc("IF(TITULO = 'grado', HISTORIAL('PORC_TITULO_GRADO'), "
                   "IF(TITULO = 'posgrado', HISTORIAL('PORC_TITULO_POSGRADO'), 0))"),
           "HISTORIAL('BASE_JEFE')", "HISTORIAL('BASE_JEFE') * UNIDAD%", ENCASILLADO),
    "31": (31, enc("IF(TITULO = 'grado' OR TITULO = 'posgrado', 0, "
                   "TABLA('PORC_TITULO_PREGRADO', COL.NIVEL <= NIVEL_PREGRADO, COL.PORC, 0))"),
           "HISTORIAL('BASE_PREGRADO')", "HISTORIAL('BASE_PREGRADO') * UNIDAD%", ENCASILLADO),
    "59": (59, enc("IF(RIESGO_ESPECIAL, HISTORIAL('PORC_RIESGO_ESPECIAL'), 0)"),
           "HISTORIAL('BASE_JEFE')", "HISTORIAL('BASE_JEFE') * UNIDAD%", ENCASILLADO),
    "83": (83, "ZONA_PORC", "TABLA('ESCALA_CLASE', COL.CLASE = ZONA_CLASE, COL.HABER, 0)",
           "TABLA('ESCALA_CLASE', COL.CLASE = ZONA_CLASE, COL.HABER, 0) * UNIDAD%", None),
    "80": (80, enc("ANIOS_ANTIGUEDAD"), "#10", "#10 * HISTORIAL('PORC_ANTIGUEDAD')% * UNIDAD", ENCASILLADO),
    "90": (90, enc_param("PORC_ADIC_FZA_SEG"), f"{BASE} + #66", f"({BASE} + #66) * UNIDAD%", ENCASILLADO),
    "64": (64, None, None, "HISTORIAL('MONTO_64')", ENCASILLADO),
    "91": (91, enc_param("PORC_AUM_0705"), f"{BASE} + #90 + #64", f"({BASE} + #90 + #64) * UNIDAD%", ENCASILLADO),
    "95": (95, enc("CUERPO_APOYO_PORC"), f"{BASE} + #90 + #64 + #91", f"({BASE} + #90 + #64 + #91) * UNIDAD%", ENCASILLADO),
    "92": (92, enc_param("PORC_AUM_0907"), f"{BASE} + #90 + #64 + #91 + #95",
           f"({BASE} + #90 + #64 + #91 + #95) * UNIDAD%", ENCASILLADO),
    "93": (93, enc_param("PORC_AUM_0308"), f"{BASE} + #90 + #64 + #91 + #95 + #92",
           f"({BASE} + #90 + #64 + #91 + #95 + #92) * UNIDAD%", ENCASILLADO),
    "50": (50, None, None, "HISTORIAL('MONTO_50')", ENCASILLADO),
    "51": (51, enc_param("PORC_PERS_SEG_2022"), "HISTORIAL('BASE_JEFE')", "HISTORIAL('BASE_JEFE') * UNIDAD%", ENCASILLADO),
    "52": (52, enc_param("PORC_FORTALECIMIENTO"), "#10", "#10 * UNIDAD%", ENCASILLADO),
    "65": (65, None, None, "IF(ADICIONAL_SEGURIDAD OR CAMPO_PRESENTE, HISTORIAL('MONTO_65'), 0)", ENCASILLADO),
    "66": (66, None, None, "HISTORIAL('MONTO_66')", ENCASILLADO),
    "73": (73, None, None, "HISTORIAL('MONTO_73')", ENCASILLADO),
    "74": (74, None, None, "#73", ENCASILLADO),
    "75": (75, None, None, "HISTORIAL('MONTO_75')", ENCASILLADO),
}

# Servicio penitenciario (verificado contra 7 liquidaciones proyectadas): el 026/027/031 van sobre la propia clase,
# el 90 no suma el 066 en su base, el 74 es un monto propio (= 73 en 2022, 73/2 en 2025). Solo se liquida lo encasillado.
JEFE_PEN = "HISTORIAL('BASE_JEFE_PEN')"
TITULO_PEN = "HISTORIAL('BASE_TITULO_PEN', FECHA, HISTORIAL('BASE_JEFE_PEN'))"
ESCALA_PEN = "TABLA('ESCALA_CLASE_PEN', COL.CLASE = {}, COL.HABER{})"
HABER_PEN: Dict[str, tuple] = {
    "10": (10, "Clase", "CLASE", None, ESCALA_PEN.format("CLASE", ""), None),
    "26": (26, "Insalubridad / Suplemento de riesgo", "CAMPO_UNIDAD", "#10", "#10 * UNIDAD%", "CAMPO_PRESENTE"),
    "23": (23, "Resp. Penitenciaria", "CAMPO_UNIDAD", JEFE_PEN, f"{JEFE_PEN} * UNIDAD%", "CAMPO_PRESENTE"),
    "27": (27, "Riesgo Especial Penitenciario", "CAMPO_UNIDAD", "#10", "#10 * UNIDAD%", "CAMPO_PRESENTE"),
    "58": (58, "Recargo de Servicio", "CAMPO_UNIDAD", JEFE_PEN, f"{JEFE_PEN} * UNIDAD%", "CAMPO_PRESENTE"),
    "24": (24, "Título de Grado / Posgrado o Resp. Profesional", "CAMPO_UNIDAD", TITULO_PEN, f"{TITULO_PEN} * UNIDAD%",
           "CAMPO_PRESENTE"),
    "31": (31, "Título Sec. y Pre-Grado", "CAMPO_UNIDAD", "#10", "#10 * UNIDAD%", "CAMPO_PRESENTE"),
    "83": (83, "Zona", "ZONA_PORC", ESCALA_PEN.format("ZONA_CLASE", ", 0"),
           ESCALA_PEN.format("ZONA_CLASE", ", 0") + " * UNIDAD%", None),
    "80": (80, "Antigüedad", enc("ANIOS_ANTIGUEDAD"), "#10", "#10 * HISTORIAL('PORC_ANTIGUEDAD_PEN')% * UNIDAD", None),
    "90": (90, "Adic Fuerza Seguridad (presentismo)", enc_param("PORC_ADIC_FZA_SEG_PEN"), BASE_PEN,
           f"({BASE_PEN}) * UNIDAD%", "CAMPO_PRESENTE"),
    "91": (91, "Aumento 07/05", enc_param("PORC_AUM_0705_PEN"), f"{BASE_PEN} + #90", f"({BASE_PEN} + #90) * UNIDAD%",
           "CAMPO_PRESENTE"),
    "92": (92, "Aumento 09/07", enc_param("PORC_AUM_0907_PEN"), f"{BASE_PEN} + #90 + #91",
           f"({BASE_PEN} + #90 + #91) * UNIDAD%", "CAMPO_PRESENTE"),
    "93": (93, "Aumento 03/08", enc_param("PORC_AUM_0308_PEN"), f"{BASE_PEN} + #90 + #91 + #92",
           f"({BASE_PEN} + #90 + #91 + #92) * UNIDAD%", "CAMPO_PRESENTE"),
    "50": (50, "Adicional Paritaria 2022", None, None, "HISTORIAL('MONTO_50_PEN')", "CAMPO_PRESENTE"),
    "51": (51, "Adicional Personal de Seguridad 2022", enc_param("PORC_PERS_SEG_2022_PEN"), JEFE_PEN,
           f"{JEFE_PEN} * UNIDAD%", "CAMPO_PRESENTE"),
    "52": (52, "A. Fortalecimiento de la Labor Polic", enc_param("PORC_FORTALECIMIENTO_PEN"), "#10", "#10 * UNIDAD%",
           "CAMPO_PRESENTE"),
    "100": (100, "Tiempo Mínimo en el Grado", None, None, "CAMPO_IMPORTE", "CAMPO_PRESENTE"),
    "65": (65, "Adicional Ley 7666", None, None, "HISTORIAL('MONTO_65_PEN')", "CAMPO_PRESENTE"),
    "66": (66, "Aumento Marzo/2010", None, None, "HISTORIAL('MONTO_66_PEN')", "CAMPO_PRESENTE"),
    "73": (73, "Adicional Aumento 07/11 / Refrigerio Penitenciario", None, None, "HISTORIAL('MONTO_73_PEN')", "CAMPO_PRESENTE"),
    "74": (74, "Adicional Aumento 07/11 / Aumento 2004", None, None, "HISTORIAL('MONTO_74_PEN')", "CAMPO_PRESENTE"),
    "75": (75, "Adicional Aumento 2004", None, None, "HISTORIAL('MONTO_75_PEN')", "CAMPO_PRESENTE"),
}

# % de retiro: manual, o tabla por la antigüedad final del cómputo de servicios (sin cómputo, los años del cargo)
PORC_RETIRO = ("IF(PORCENTAJE_RETIRO_MANUAL > 0, PORCENTAJE_RETIRO_MANUAL, "
               "IF(TIPO_PERSONAL = 'superior', "
               "TABLA('RETIRO_SUPERIOR', COL.ANIOS <= ANTIGUEDAD_FINAL, COL.PORC, 0), "
               "TABLA('RETIRO_SUBALTERNO', COL.ANIOS <= ANTIGUEDAD_FINAL, COL.PORC, 0)))")

# codigo: (descripcion, columna, etapa, orden, formula_importe, decimales, tipo_beneficio)
# HABER_PONDERADO = suma de (total remunerativo de cada cargo x % de su secuencia); lo calcula el liquidador.
DERIVADOS: Dict[str, tuple] = {
    "HABER_RETIRO": ("Haber de retiro", "AUXILIAR", "beneficio", 1000, "HABER_PONDERADO * UNIDAD%", HAB, None),
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


def _concepto(db: Session, codigo: str, force: bool, escalafon: str = "policia", **campos) -> Concepto:
    c = db.exec(select(Concepto).where(Concepto.codigo == codigo, Concepto.escalafon == escalafon)).first()
    if c is None:
        c = Concepto(codigo=codigo, escalafon=escalafon, **campos)
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
    for codigo, (orden, unidad, unitario, importe, condicion) in HABER.items():
        c = _concepto(db, codigo, force, descripcion=nombres.get(codigo, codigo), columna="REMUNERATIVO", etapa="haber",
                      formula_unidad=unidad, formula_unitario=unitario, formula_importe=importe,
                      formula_condicion=condicion, decimales_importe=HAB, orden=orden)
        _vigencias(db, c, data["presencia"][codigo], None, force)

    # Conceptos derivados (retiro, pensión, descuentos de la liquidación)
    for codigo, (desc, columna, etapa, orden, formula, dec, tipo) in DERIVADOS.items():
        extra = _RETIRO if codigo == "HABER_RETIRO" else {}
        c = _concepto(db, codigo, force, descripcion=desc, columna=columna, etapa=etapa,
                      formula_importe=formula, decimales_importe=dec, orden=orden, **extra)
        _vigencias(db, c, [{"desde": DESDE.isoformat(), "hasta": None}], tipo, force)

    vig_pen = seed_proyectadas(db, force)
    db.commit()
    return {"vigencias": data["cobertura"]["vigencias"], "desde": data["cobertura"]["desde"], "proyectadas": vig_pen}


# HABER_RETIRO muestra el % de retiro (unidad) y el haber ponderado (base), como la planilla proyectada
_RETIRO = {"formula_unidad": PORC_RETIRO, "formula_unitario": "HABER_PONDERADO"}


def seed_proyectadas(db: Session, force: bool = False) -> int:
    """Juego penitenciario y escalas/parámetros PARCIALES deducidos de las liquidaciones proyectadas relevadas."""
    if not DATA_PROYECTADAS.exists():
        return 0
    data = json.loads(DATA_PROYECTADAS.read_text(encoding="utf-8"))
    desc = f"PROVISORIA – casos relevados ({data['fuente']}): solo las clases/valores que aparecen en las liquidaciones"
    cols = [{"nombre": "CLASE", "tipo": "int"}, {"nombre": "HABER", "tipo": "decimal"}]
    for v in data["vigencias"]:
        codigo = "ESCALA_CLASE_PEN" if v["escalafon"] == "penitenciario" else "ESCALA_CLASE"
        filas = [[int(k), str(x)] for k, x in v["escala"].items()]
        _crear_tabla(db, codigo, desc, cols, filas, _d(v["desde"]), _d(v["hasta"]), force)
        for campo, valor in v["parametros"].items():
            _param(db, campo, valor, _d(v["desde"]), _d(v["hasta"]), desc, force)

    for codigo, (orden, descripcion, unidad, unitario, importe, condicion) in HABER_PEN.items():
        c = _concepto(db, codigo, force, escalafon="penitenciario", descripcion=descripcion, columna="REMUNERATIVO",
                      etapa="haber", formula_unidad=unidad, formula_unitario=unitario, formula_importe=importe,
                      formula_condicion=condicion, decimales_importe=HAB, orden=orden)
        _vigencias(db, c, [{"desde": DESDE_PEN.isoformat(), "hasta": None}], None, force)
    d = DERIVADOS["HABER_RETIRO"]
    c = _concepto(db, "HABER_RETIRO", force, escalafon="penitenciario", descripcion=d[0], columna=d[1], etapa=d[2],
                  formula_importe=d[4], decimales_importe=d[5], orden=d[3], **_RETIRO)
    _vigencias(db, c, [{"desde": DESDE_PEN.isoformat(), "hasta": None}], None, force)
    return len(data["vigencias"])


if __name__ == "__main__":
    with Session(engine) as session:
        info = seed_reglas(session, force="--force" in sys.argv)
    print(f"Reglas cargadas: {info['vigencias']} vigencias desde {info['desde']} "
          f"+ {info['proyectadas']} vigencias parciales de liquidaciones proyectadas")
