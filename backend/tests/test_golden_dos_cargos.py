"""Paridad con la planilla "BASE DE CALCULOS PENSION 2 CARGOS" (hoja LIQUIDACION: pensión total).

Valores esperados generados con `scripts/golden_dos_cargos.py` recalculando el Excel con LibreOffice.
Rango: 2022-07-01 .. 2024-12-31 (35 meses, 5 SAC). La pensión de un solo beneficiario al 100% coincide con la
"pensión total" de la planilla.
"""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models.models  # noqa: F401
from app.db.seed_reglas import seed_reglas
from app.models import prevision as m
from app.services import motor
from app.services.liquidador import calcular_liquidacion
from app.services.resumen import armar_resumen
from tests.golden_utils import TOL_MES, TOL_TOTAL, cerca, mensual_excel, mensual_sistema

pytestmark = pytest.mark.skipif(motor._engine is None, reason="otp_engine no instalado")

GOLDEN = json.loads((Path(__file__).parent / "golden" / "casos_dos_cargos.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_reglas(session)
        yield session


def _armar(db, caso):
    c = m.Causante(dni=str(abs(hash(caso["nombre"])))[:8], apellido="Golden", nombre=caso["nombre"][:20], tipo_personal="superior")
    db.add(c)
    db.commit()
    db.refresh(c)
    for cargo in caso["cargos"]:
        db.add(m.CargoSecuencia(causante_id=c.id, **cargo))
    db.add(m.Beneficiario(causante_id=c.id, apellido="B", nombre="Beneficiario", **caso["beneficiario"]))
    liq = m.Liquidacion(causante_id=c.id, periodo="2024-12", tipo="pension",
                        fecha_desde=date.fromisoformat(GOLDEN["rango"]["desde"]), fecha_hasta=date.fromisoformat(GOLDEN["rango"]["hasta"]),
                        anticipo_importe=Decimal(str(caso.get("anticipo", 0))))
    db.add(liq)
    db.commit()
    db.refresh(liq)
    calcular_liquidacion(db, liq.id)
    return armar_resumen(db, liq.id)


@pytest.mark.parametrize("caso", GOLDEN["casos"], ids=lambda c: c["nombre"])
def test_paridad_pension_dos_cargos(db, caso):
    resumen = _armar(db, caso)
    assert len(resumen["recibos"]) == 1
    rec, esp = resumen["recibos"][0], caso["esperado"]
    nombre = caso["nombre"]

    mens_excel, mens_sis = mensual_excel(esp), mensual_sistema(rec["tramos"])
    assert mens_excel.keys() == mens_sis.keys(), nombre
    for mes in sorted(mens_excel):
        cerca(mens_sis[mes], mens_excel[mes], TOL_MES, f"{nombre} pensión {mes}")

    sac = [Decimal(t["importe"]) for t in rec["tramos"] if t["es_sac"]]
    assert len(sac) == len(esp["sacs"]) == 5
    for i, (s, e) in enumerate(zip(sac, esp["sacs"])):
        cerca(s, e["importe"], TOL_MES, f"{nombre} SAC #{i + 1}")

    cerca(rec["credito"], esp["subtotal_credito"], TOL_TOTAL, f"{nombre} subtotal crédito")
    anticipo = Decimal(str(caso.get("anticipo", 0)))
    cerca(Decimal(rec["total_descuentos"]) - anticipo, esp["descuentos"], TOL_TOTAL, f"{nombre} descuentos OSEP")
    cerca(rec["liquido"], esp["liquido"], TOL_TOTAL, f"{nombre} líquido")

    # el resumen expone el haber ponderado y el aporte de cada secuencia
    assert [c["secuencia"] for c in rec["cargos"]] == [1, 2]
    ponderado = sum(Decimal(c["total"]) * Decimal(c["porcentaje"]) / 100 for c in rec["cargos"])
    cerca(rec["haber_ponderado"], ponderado, Decimal("0.0001"), f"{nombre} haber ponderado")
    assert {c["secuencia"] for c in rec["conceptos_haber"]} == {1, 2, None}
