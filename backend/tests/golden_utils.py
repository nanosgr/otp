"""Utilidades compartidas por los tests de paridad con las planillas de Excel."""
from datetime import date
from decimal import Decimal

TOL_MES = Decimal("0.01")     # haber mensual y SAC
TOL_TOTAL = Decimal("0.02")   # subtotal, descuentos y líquido (los descuentos se redondean al centavo por línea)


def meses_de(desde: date, cantidad: int):
    y, mth = desde.year, desde.month
    for _ in range(cantidad):
        yield f"{y}-{mth:02d}"
        y, mth = (y + 1, 1) if mth == 12 else (y, mth + 1)


def mensual_excel(esperado) -> dict:
    out = {}
    for t in esperado["tramos"]:
        for mes in meses_de(date.fromisoformat(t["desde"]), int(t["meses"])):
            out[mes] = Decimal(str(t["nominal"]))
    return out


def mensual_sistema(tramos) -> dict:
    out = {}
    for t in tramos:
        if t["es_sac"]:
            continue
        d, h = date.fromisoformat(t["desde"]), date.fromisoformat(t["hasta"])
        n = (h.year - d.year) * 12 + h.month - d.month + 1
        for mes in meses_de(date(d.year, d.month, 1), n):
            out[mes] = Decimal(t["haber_mensual"])
    return out


def cerca(a, b, tol, msg):
    assert abs(Decimal(str(a)) - Decimal(str(b))) <= tol, f"{msg}: sistema={a} excel={b}"
