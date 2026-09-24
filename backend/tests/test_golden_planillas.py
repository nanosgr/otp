"""Paridad con la planilla de la oficina técnica.

Los valores esperados (tests/golden/casos_planilla.json) se generan con `scripts/golden_planilla.py`
recalculando el Excel original con LibreOffice sobre los mismos datos de entrada; no salen de este sistema.
Rango liquidado: 2022-07-01 .. 2025-03-31 (37 meses, 5 SAC).
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

GOLDEN = json.loads((Path(__file__).parent / "golden" / "casos_planilla.json").read_text(encoding="utf-8"))
@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_reglas(session)
        yield session


def _armar(db, caso):
    causante = m.Causante(dni=str(abs(hash(caso["nombre"])))[:8], apellido="Golden", nombre=caso["nombre"][:20], **caso["causante"])
    db.add(causante)
    db.commit()
    db.refresh(causante)
    db.add(m.CargoSecuencia(causante_id=causante.id, **caso["cargo"]))
    for b in caso.get("beneficiarios", []):
        db.add(m.Beneficiario(causante_id=causante.id, apellido="B", nombre=b["parentesco"], **b))
    liq = m.Liquidacion(causante_id=causante.id, periodo="2025-03", tipo=caso["tipo"],
                        fecha_desde=date.fromisoformat(GOLDEN["rango"]["desde"]),
                        fecha_hasta=date.fromisoformat(GOLDEN["rango"]["hasta"]),
                        anticipo_importe=Decimal(str(caso.get("anticipo", 0))))
    db.add(liq)
    db.commit()
    db.refresh(liq)
    calcular_liquidacion(db, liq.id)
    return armar_resumen(db, liq.id)


@pytest.mark.parametrize("caso", GOLDEN["casos"], ids=lambda c: c["nombre"])
def test_paridad_con_planilla(db, caso):
    resumen = _armar(db, caso)
    recibos = resumen["recibos"]
    por_recibo = caso.get("esperado_por_recibo", [0] * len(recibos))
    assert len(recibos) == len(por_recibo)
    anticipo_total = Decimal(str(caso.get("anticipo", 0)))

    for n, (rec, idx) in enumerate(zip(recibos, por_recibo), start=1):
        esp = caso["esperado"][idx]
        nombre = f"{caso['nombre']} recibo {n} ({esp['hoja']})"

        # haber de cada mes
        mens_excel, mens_sis = mensual_excel(esp), mensual_sistema(rec["tramos"])
        assert mens_excel.keys() == mens_sis.keys(), nombre
        for mes in sorted(mens_excel):
            cerca(mens_sis[mes], mens_excel[mes], TOL_MES, f"{nombre} haber {mes}")

        # SAC
        sac_sis = [Decimal(t["importe"]) for t in rec["tramos"] if t["es_sac"]]
        assert len(sac_sis) == len(esp["sacs"]) == 5, nombre
        for i, (s, e) in enumerate(zip(sac_sis, esp["sacs"])):
            cerca(s, e["importe"], TOL_MES, f"{nombre} SAC #{i + 1}")

        # totales
        cerca(rec["credito"], esp["subtotal_credito"], TOL_TOTAL, f"{nombre} subtotal crédito")
        descuentos = Decimal(rec["total_descuentos"])
        anticipo = anticipo_total if len(recibos) == 1 else Decimal(0)
        if esp["descuentos_de_excel"]:
            cerca(descuentos - anticipo, esp["descuentos"], TOL_TOTAL, f"{nombre} descuentos")
            cerca(rec["liquido"], esp["liquido"], TOL_TOTAL, f"{nombre} líquido")
        else:  # B2..B5 traen un error de referencia en Excel: se verifica contra el 6% del propio subtotal
            cerca(descuentos, Decimal(str(esp["subtotal_credito"])) * Decimal("0.06"), TOL_TOTAL, f"{nombre} descuentos (6%)")
            cerca(rec["liquido"], Decimal(str(esp["subtotal_credito"])) * Decimal("0.94"), TOL_TOTAL, f"{nombre} líquido (94%)")
