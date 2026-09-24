#!/usr/bin/env python3
"""Extrae de "BASE DE LIQ RETIROS-REAJUSTES-PENSION POLICIA" las reglas por vigencia (mayo 2022 en adelante)
y las vuelca en backend/app/db/seed_data/reglas_planillas.json.

Cada hoja de período contiene bloques de 5 columnas (uno por mes de vigencia). De cada bloque se toma:
escala de clase, montos fijos, porcentajes y qué conceptos existen. Las fórmulas de los conceptos NO se
extraen: están escritas a mano en app/db/seed_reglas.py y este script verifica que los datos sean coherentes
con ellas (bases de cálculo y constantes).

Uso:  soffice --headless --convert-to xlsx "BASE DE LIQ ....xls"   (en un directorio temporal)
      python scripts/import_reglas_planillas.py <archivo.xlsx>
Requiere openpyxl.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

SHEETS = ["5,6,7-2022", "desde 8-2022", "2023", "hasta 09-2024", "desde 10-2024", "2025"]
OUT = Path(__file__).resolve().parent.parent / "backend/app/db/seed_data/reglas_planillas.json"

FIJOS = {"50": "MONTO_50", "64": "MONTO_64", "66": "MONTO_66", "73": "MONTO_73", "75": "MONTO_75"}
PORC_D = {"51": "PORC_PERS_SEG_2022", "52": "PORC_FORTALECIMIENTO"}
PORC_FORMULA = {"90": "PORC_ADIC_FZA_SEG", "91": "PORC_AUM_0705", "92": "PORC_AUM_0907", "93": "PORC_AUM_0308"}
PRESENCIA = ["10", "23", "58", "24", "31", "59", "83", "80", "90", "64", "91", "95", "92", "93",
             "50", "51", "52", "65", "66", "73", "74", "75"]


def d(v):
    return v.date() if isinstance(v, datetime) else v


def arrays(formula):
    m = re.search(r"LOOKUP\([^,]+,\{([^}]*)\},\{([^}]*)\}\)", formula)
    keys = [int(x) for x in m.group(1).split(",")]
    vals = [float(x) for x in m.group(2).split(",")]
    return dict(zip(keys, vals))


def num(v):
    return None if v is None else float(v)


def main(path):
    wb = openpyxl.load_workbook(path, data_only=False)
    bloques = []  # {desde, escala, fijos, porc, presentes, riesgo}
    nombres = {}
    for name in SHEETS:
        ws = wb[name]
        rowcode = {c.row: int(c.value) for c in ws["A"] if isinstance(c.value, (int, float)) and 7 <= c.row <= 60}
        for r, code in rowcode.items():
            nombres.setdefault(str(code), str(ws.cell(r, 2).value).strip().title())
        starts = [c.column for c in ws[5] if c.value == "VIGENCIA"]
        for b in starts:
            off = b - 2
            E = lambda code: ws.cell(next(r for r, c in rowcode.items() if c == code), 5 + off).value
            C = lambda code: ws.cell(next(r for r, c in rowcode.items() if c == code), 3 + off).value
            D = lambda code: ws.cell(next(r for r, c in rowcode.items() if c == code), 4 + off).value
            has = lambda code: code in rowcode.values() and E(code) is not None
            vig = d(ws.cell(5, b + 1).value)
            assert isinstance(vig, date), (name, b)
            escala = arrays(E(10))
            # coherencias con las fórmulas del seed
            # Base "Jefe de Policía" (C9): desde ago/2022 coincide con la clase 21; en may-jul/2022 es un valor
            # propio que no figura en la escala. La base de pregrado (C15) coincide siempre con la clase 17.
            if 21 in escala:
                assert abs(C(23) - escala[21]) < 0.006, (name, vig, "base jefe != clase 21")
            assert abs(C(31) - escala[17]) < 0.006, (name, vig, "base pregrado != clase 17")
            assert re.search(r"[A-Z]+\d+\*2%\*[A-Z]+\d+", str(E(80))), (name, vig, "antigüedad != clase*2%*años")
            fijos, porc = {}, {}
            for code, campo in FIJOS.items():
                if has(int(code)):
                    fijos[campo] = num(E(int(code)))
            m = re.match(r"=\s*([0-9.]+)\*[A-Z]+\d+", str(E(65)))
            assert m, (name, vig, E(65))
            fijos["MONTO_65"] = float(m.group(1))
            fijos["BASE_JEFE"] = num(C(23))
            fijos["BASE_PREGRADO"] = num(C(31))
            for code, campo in PORC_D.items():
                if has(int(code)):
                    porc[campo] = num(D(int(code))) * 100
            for code, campo in PORC_FORMULA.items():
                m = re.search(r"\*\s*([0-9.]+)\s*$", str(E(int(code))))
                assert m, (name, vig, code, E(int(code)))
                porc[campo] = round(float(m.group(1)) * 100, 6)
            if has(74) or has(73):
                v74 = E(74)
                igual = (isinstance(v74, (int, float)) and abs(v74 - E(73)) < 0.006) or (
                    isinstance(v74, str) and v74.endswith(f"{get_column_letter(5 + off)}{next(r for r, c in rowcode.items() if c == 73)}"))
                assert has(74) and has(73) and igual, (name, vig, "74 != 73")
            # riesgo especial: 6,5% hasta 06/2024 y 13% desde 07/2024 (rótulos de DATOS); se verifica a qué celda apunta
            ref = str(D(59)).replace("$", "")
            riesgo = 6.5 if "D61" in ref else 13.0 if "D63" in ref else None
            assert riesgo is not None, (name, vig, ref)
            porc["PORC_RIESGO_ESPECIAL"] = riesgo
            porc["PORC_ANTIGUEDAD"] = 2.0
            presentes = [str(c) for c in PRESENCIA if int(c) in rowcode.values() and has(int(c))]
            bloques.append({"desde": vig, "escala": escala, "fijos": fijos, "porc": porc, "presentes": presentes})
    # Tablas de % de retiro por años de servicio (DATOS!J26:K46 y M26:N46), en porcentaje 0-100
    datos = wb["DATOS"]
    retiro = {}
    for nombre, (ca, cp) in {"K": ("J", "K"), "N": ("M", "N")}.items():
        filas = []
        for r in range(26, 47):
            a, pct = datos[f"{ca}{r}"].value, datos[f"{cp}{r}"].value
            if a is not None and pct is not None:
                filas.append([int(a), round(float(pct) * 100, 6)])
        assert filas and filas[0][0] == 10, nombre
        retiro[nombre] = filas
    bloques.sort(key=lambda x: x["desde"])
    fechas = [b["desde"] for b in bloques]
    assert len(set(fechas)) == len(fechas), "vigencias duplicadas"

    def hasta_de(i):
        return None if i == len(bloques) - 1 else bloques[i + 1]["desde"] - timedelta(days=1)

    def comprimir(serie):  # [(desde, hasta, valor)] -> une consecutivos con igual valor
        out = []
        for desde, hasta, v in serie:
            if out and out[-1][2] == v:
                out[-1] = (out[-1][0], hasta, v)
            else:
                out.append((desde, hasta, v))
        return out

    escalas = [{"desde": b["desde"].isoformat(), "hasta": hasta_de(i) and hasta_de(i).isoformat(),
                "clases": {str(k): v for k, v in sorted(b["escala"].items())}} for i, b in enumerate(bloques)]
    escalas = [dict(e, clases=e["clases"]) for e in escalas]  # una escala por vigencia (cambian todos los meses)
    parametros = defaultdict(list)
    campos = sorted({c for b in bloques for c in list(b["fijos"]) + list(b["porc"])})
    for campo in campos:
        serie = []
        for i, b in enumerate(bloques):
            v = b["fijos"].get(campo, b["porc"].get(campo))
            if v is not None:
                serie.append((b["desde"], hasta_de(i), v))
        # un campo ausente en un bloque corta la vigencia: no se "rellena" el hueco
        for desde, hasta, v in comprimir(serie):
            parametros[campo].append({"desde": desde.isoformat(), "hasta": hasta.isoformat() if hasta else None, "valor": v})
    presencia = {}
    for code in PRESENCIA:
        serie = [(b["desde"], hasta_de(i), code in b["presentes"]) for i, b in enumerate(bloques)]
        presencia[code] = [{"desde": a.isoformat(), "hasta": h.isoformat() if h else None}
                           for a, h, v in comprimir(serie) if v]
    data = {
        "fuente": "BASE DE LIQ RETIROS-REAJUSTES-PENSION POLICIA.xls (hojas 5,6,7-2022 a 2025)",
        "cobertura": {"desde": fechas[0].isoformat(), "vigencias": len(bloques)},
        "nombres": nombres,
        "escalas": escalas,
        "parametros": dict(parametros),
        "presencia": presencia,
        "retiro_por_anios": retiro,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(bloques)} vigencias ({fechas[0]} .. {fechas[-1]}) -> {OUT}")
    for code, rangos in presencia.items():
        print(f"  concepto {code:>3}: {[(r['desde'], r['hasta']) for r in rangos]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
