"""Tests del wrapper Python del motor Rust (se omiten si el wheel no está instalado)."""
from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("otp_engine")

from app.services import motor  # noqa: E402


def test_calculo_con_decimal_y_fechas():
    reglas = {"conceptos": [
        {"codigo": "10", "columna": "REMUNERATIVO", "formula_importe": "HABER * 2%"},
        {"codigo": "80", "columna": "REMUNERATIVO", "formula_unidad": "ANIOS(INGRESO, FECHA)", "formula_unitario": "#10"},
        {"codigo": "90", "columna": "DESCUENTO", "formula_importe": "TOTAL('REMUNERATIVO') * 8%"},
    ]}
    ctx = {"fecha": date(2025, 3, 1), "variables": {"HABER": Decimal("1000.10"), "INGRESO": date(2005, 3, 1)}}
    r = motor.calcular(reglas, ctx)
    por_codigo = {c["codigo"]: c for c in r["conceptos"]}
    assert Decimal(por_codigo["10"]["importe"]) == Decimal("20.00")
    assert Decimal(por_codigo["80"]["unidad"]) == 20
    assert Decimal(por_codigo["80"]["importe"]) == Decimal("400.00")
    assert Decimal(r["totales"]["neto"]) == Decimal("386.40")


def test_no_pierde_precision_decimal():
    r = motor.calcular({"conceptos": [{"codigo": "1", "formula_importe": "X"}]},
                       {"fecha": date(2025, 1, 1), "variables": {"X": Decimal("0.1") + Decimal("0.2")}})
    assert r["conceptos"][0]["importe"] == "0.30"


def test_validacion():
    assert motor.validar_formula("TOTAL('X') + #10")["conceptos"] == ["10"]
    with pytest.raises(motor.FormulaError):
        motor.validar_formula("1 +")
    problemas = motor.validar_reglas({"conceptos": [
        {"codigo": "A", "formula_importe": "#B"}, {"codigo": "B", "formula_importe": "#A"}]})
    assert sum(p["nivel"] == "error" for p in problemas) == 2


def test_tipo_no_serializable():
    with pytest.raises(TypeError):
        motor.calcular({"conceptos": []}, {"fecha": date(2025, 1, 1), "variables": {"X": object()}})
