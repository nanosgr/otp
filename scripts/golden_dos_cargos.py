#!/usr/bin/env python3
"""Casos dorados de pensión con dos cargos, recalculando "BASE DE CALCULOS PENSION 2 CARGOS" con LibreOffice.

Carga cada caso en DATOS (columna D = secuencia 1, columna E = secuencia 2), deja en la hoja `LIQUIDACION `
(pensión total, sin dividir por beneficiario) solo los tramos de jul/2022 a dic/2024 (35 meses, 5 SAC) y guarda los
valores esperados en backend/tests/golden/casos_dos_cargos.json. Los valores NO salen del motor propio.

La planilla trae dos defectos que se corrigen en la copia de trabajo (y se informan en el JSON):
  * nov/2024: "Aumento Marzo/2010" (concepto 66) quedó en 8110,48; la otra planilla y la progresión de la
    paritaria dan 8345,57;
  * la tabla de la base de zona (concepto 83, `LOOKUP`) quedó desactualizada en abr-may/2023 y con un valor mal
    tipeado en jul/2024 (clase 5: 105213,03 en lugar de 105513,03): se reemplaza por la escala de clase de su bloque;
  * filas que suman dos veces la misma celda (`=+X+X`), si las hubiera.

Uso:  python scripts/golden_dos_cargos.py <BASE DE CALCULOS PENSION 2 CARGOS.xlsx convertido>
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl
from openpyxl.cell.cell import MergedCell

OUT = Path(__file__).resolve().parent.parent / "backend/tests/golden/casos_dos_cargos.json"
HOJA = "LIQUIDACION "
FILAS = range(75, 110)                                   # jul/2022 .. dic/2024
LIMPIAR = list(range(14, 75)) + [110, 111]
RANGO = {"desde": "2022-07-01", "hasta": "2024-12-31"}
MONTO_66_NOV_2024 = (8110.48, 8345.57)
DUPLICADA = re.compile(r"^=\+?(.+)\+\1$")

CASOS = [
    {
        "nombre": "dos_cargos_60_40_clase16_y_clase12",
        "cargos": [
            {"secuencia": 1, "porcentaje_secuencia": 60, "clase": 16, "responsabilidad_jerarquica_porcentaje": 81.01,
             "titulo": "grado", "riesgo_especial": True, "zona_porcentaje": 10, "zona_clase": 16, "anios_antiguedad": 30,
             "adicional_seguridad": True, "porcentaje_retiro": 100},
            {"secuencia": 2, "porcentaje_secuencia": 40, "clase": 12, "titulo": "ninguno", "titulo_pregrado_nivel": 1,
             "anios_antiguedad": 20, "cuerpo_apoyo_porcentaje": 5, "adicional_seguridad": False},
        ],
        "beneficiario": {"parentesco": "conyuge", "porcentaje": 100},
        "anticipo": 0,
    },
    {
        "nombre": "dos_cargos_70_30_con_retiro_parcial_y_anticipo",
        "cargos": [
            {"secuencia": 1, "porcentaje_secuencia": 70, "clase": 20, "responsabilidad_jerarquica_porcentaje": 100,
             "titulo": "posgrado", "anios_antiguedad": 27, "adicional_seguridad": True, "porcentaje_retiro": 87},
            {"secuencia": 2, "porcentaje_secuencia": 30, "clase": 9, "titulo": "ninguno", "titulo_pregrado_nivel": 2,
             "anios_antiguedad": 10, "riesgo_especial": True},
        ],
        "beneficiario": {"parentesco": "conyuge", "porcentaje": 100},
        "anticipo": 120000,
    },
]


def cargar_datos(wb, caso):
    ds = wb["DATOS"]
    for col, c in zip("DE", caso["cargos"]):
        ds[f"{col}32"] = c["clase"]
        for fila in (34, 36):
            ds[f"{col}{fila}"] = c.get("responsabilidad_jerarquica_porcentaje", 0) / 100
        ds[f"{col}40"] = c.get("recargo_servicio_porcentaje", 0) / 100
        ds[f"{col}42"] = {"ninguno": 0, "grado": 0.20, "posgrado": 0.25}[c.get("titulo", "ninguno")]
        ds[f"{col}44"] = c.get("titulo_pregrado_nivel", 0)
        riesgo = c.get("riesgo_especial", False)
        ds[f"{col}47"] = 0.065 if riesgo else 0
        ds[f"{col}49"] = 0.13 if riesgo else 0
        ds[f"{col}51"] = c.get("zona_porcentaje", 0) / 100
        ds[f"{col}52"] = c.get("zona_clase", 0)
        ds[f"{col}54"] = c.get("anios_antiguedad", 0)
        ds[f"{col}60"] = c.get("cuerpo_apoyo_porcentaje", 0) / 100
        ds[f"{col}62"] = 1 if c.get("adicional_seguridad") else 0
        ds[f"{col}64"] = 0
        ds[f"{col}68"] = c["porcentaje_secuencia"] / 100
    ds["E66"] = caso["cargos"][0].get("porcentaje_retiro", 0) / 100
    b = caso["beneficiario"]
    ds["D6"] = b["porcentaje"] / 100
    for celda in ("D11", "D16", "D21"):
        ds[celda] = 0
    for celda in ("C14", "C19", "C24"):
        ds[celda] = 0


HOJAS_PERIODO = ["5,6,7-2022", "desde 8-2022", "2023", "hasta 09-2024", "desde 10-2024"]
ARREGLOS = re.compile(r"\{([^}]*)\},\{([^}]*)\}")


def corregir_zona(wb):
    """La base de zona debe usar la misma escala de clase que el bloque; se reescribe si difiere."""
    corr = []
    for nombre in HOJAS_PERIODO:
        ws = wb[nombre]
        filas = {int(c.value): c.row for c in ws["A"] if isinstance(c.value, (int, float)) and 6 <= c.row <= 62}
        r10, r83 = filas[10], filas[83]
        for c in ws[6]:
            if c.value != "VIGENCIA" or not ws.cell(6, c.column + 1).value:
                continue
            for off in (c.column - 2, c.column + 3):                     # secuencia 1 y secuencia 2
                clase, zona = ws.cell(r10, 5 + off), ws.cell(r83, 3 + off)
                mc, mz = ARREGLOS.search(str(clase.value)), ARREGLOS.search(str(zona.value))
                if not (mc and mz):
                    continue
                esperado = "0," + mc.group(2)
                if mz.group(2) != esperado:
                    original = [float(x) for x in mz.group(2).split(",")]
                    nuevo = [float(x) for x in esperado.split(",")]
                    dif = [(k, a, b) for k, a, b in zip(("0," + mc.group(1)).split(","), original, nuevo) if abs(a - b) > 0.005]
                    zona.value = zona.value.replace(mz.group(2), esperado)
                    corr.append({"hoja": nombre, "celda": zona.coordinate, "motivo": "tabla de zona distinta de la escala de clase",
                                 "clases_distintas": len(dif), "ejemplo": dif[0]})
    return corr


def corregir_planilla(wb):
    """Devuelve la lista de correcciones aplicadas a la copia de trabajo."""
    corr = corregir_zona(wb)
    ws = wb["desde 10-2024"]
    rowcode = {c.row: c.value for c in ws["A"] if isinstance(c.value, (int, float))}
    r66 = next(r for r, c in rowcode.items() if c == 66)
    for c in ws[6]:
        if c.value != "VIGENCIA":
            continue
        vig = ws.cell(6, c.column + 1).value
        if vig and vig.date().isoformat() == "2024-11-01":
            celda = ws.cell(r66, c.column + 3)
            if celda.value == MONTO_66_NOV_2024[0]:
                corr.append({"hoja": "desde 10-2024", "celda": celda.coordinate, "original": celda.value,
                             "corregida": MONTO_66_NOV_2024[1], "motivo": "aumento marzo/2010 desactualizado en nov/2024"})
                celda.value = MONTO_66_NOV_2024[1]
    ws = wb[HOJA]
    for r in FILAS:
        v = ws[f"A{r}"].value
        m = DUPLICADA.match(v) if isinstance(v, str) else None
        if m:
            ws[f"A{r}"] = "=+" + m.group(1)
            corr.append({"hoja": HOJA, "celda": f"A{r}", "original": v, "corregida": "=+" + m.group(1), "motivo": "celda sumada dos veces"})
    return corr


def preparar(wb, caso):
    ws = wb[HOJA]
    for r in LIMPIAR:
        for idx in range(1, 7):
            celda = ws.cell(r, idx)
            if not isinstance(celda, MergedCell):
                celda.value = None
    ws["D122"] = caso.get("anticipo", 0)
    ws["D125"] = 0


def leer(ws):
    tramos, sacs = [], []
    for r in FILAS:
        a, b, dmes, f = (ws[f"{col}{r}"].value for col in "ABDF")
        if b == "SAC":
            sacs.append({"fila": r, "importe": f})
        else:
            tramos.append({"fila": r, "desde": b.date().isoformat(), "meses": dmes, "nominal": a, "total": f})
    return {"tramos": tramos, "sacs": sacs, "subtotal_credito": ws["F112"].value, "descuentos": ws["D119"].value,
            "liquido": ws["D126"].value}


def main(src):
    resultado = {"rango": RANGO, "fuente": Path(src).name, "casos": []}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for caso in CASOS:
            wb = openpyxl.load_workbook(src)
            cargar_datos(wb, caso)
            correcciones = corregir_planilla(wb)
            preparar(wb, caso)
            f_in = tmp / f"{caso['nombre']}.xlsx"
            wb.save(f_in)
            out = tmp / "out"
            out.mkdir(exist_ok=True)
            subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(out), str(f_in)],
                           check=True, capture_output=True, timeout=300)
            esperado = leer(openpyxl.load_workbook(out / f_in.name, data_only=True)[HOJA])
            assert isinstance(esperado["subtotal_credito"], (int, float)) and isinstance(esperado["liquido"], (int, float)), esperado
            resultado["casos"].append(caso | {"esperado": esperado, "correcciones_planilla": correcciones})
            print(caso["nombre"], round(esperado["subtotal_credito"], 2), round(esperado["liquido"], 2), f"({len(correcciones)} correcciones)")
    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("->", OUT)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
