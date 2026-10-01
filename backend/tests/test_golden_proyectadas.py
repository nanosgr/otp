"""Paridad con las 10 liquidaciones proyectadas de renuncia/baja condicionada relevadas (policía y penitenciaría).

Datos y valores esperados (transcriptos de los PDF de la oficina): `app/db/seed_data/casos_proyectados.json`, generado
con `scripts/import_casos_proyectados.py`. Compara importe por concepto, total de haberes, % y haber de retiro,
antigüedad final del cómputo y % de zona del anexo.
"""
import json
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models.models  # noqa: F401
from app.db.seed_casos_proyectados import DATA, cargar_caso
from app.db.seed_reglas import seed_reglas
from app.models import prevision as m
from app.services import motor
from app.services.computo import computo
from app.services.zona import calcular_zona

pytestmark = pytest.mark.skipif(motor._engine is None, reason="otp_engine no instalado")

CASOS = json.loads(DATA.read_text(encoding="utf-8"))["casos"]
TOL_CONCEPTO = Decimal("0.01")
# La planilla suma importes sin redondear y muestra cada uno redondeado; en CORRENTI el total del PDF queda 0,0235
# por debajo de la suma sin redondear (la suma de los importes mostrados da 0,02 más que el total).
TOL_TOTAL = Decimal("0.03")
# Diferencias conocidas del PDF contra la planilla de retroactivos (ver CLAUDE.md, supuestos de la proyectada):
# BERON trae 064 = 848,28 y la planilla de retroactivos 07/2022, 848,25 (arrastra ~0,045 al total).
EXCEPCIONES = {("BERON FLORES", "64"): Decimal("0.05")}


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_reglas(session)
        yield session


def D(x) -> Decimal:
    return Decimal(str(x or 0))


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c["hoja"])
def test_paridad_liquidacion_proyectada(db, caso):
    liq = cargar_caso(db, caso)
    recibo = db.exec(select(m.Recibo).where(m.Recibo.liquidacion_id == liq.id)).one()
    filas = db.exec(select(m.ReciboConcepto).where(m.ReciboConcepto.recibo_id == recibo.id)).all()
    haber = {f.codigo: f for f in filas if f.secuencia == 1}
    esp = caso["esperado"]

    errores = []
    for codigo, importe in esp["conceptos"].items():
        obtenido = haber[codigo].importe if codigo in haber else Decimal(0)
        tol = EXCEPCIONES.get((caso["hoja"], codigo), TOL_CONCEPTO)
        if abs(obtenido - D(importe)) > tol:
            errores.append(f"{codigo}: {obtenido} != {importe}")
    sobrantes = [c for c, f in haber.items() if c not in esp["conceptos"] and f.importe != 0]
    assert not errores and not sobrantes, f"{caso['hoja']}: {errores} sobrantes={sobrantes}"

    tol = TOL_TOTAL + sum((t for (h, _), t in EXCEPCIONES.items() if h == caso["hoja"]), Decimal(0))
    retiro = next(f for f in filas if f.codigo == "HABER_RETIRO")
    assert abs(retiro.unitario - D(esp["total_haberes"])) <= tol        # haber (ponderado) = total de haberes
    assert retiro.unidad == D(esp["porcentaje_retiro"])
    assert abs(retiro.importe - D(esp["haber_retiro"])) <= tol
    assert abs(liq.total_liquido - D(esp["haber_retiro"])) <= tol

    snap = recibo.snapshot
    assert snap["computo"]["antiguedad_final"] == esp["computo"]["antiguedad_final"]
    if esp["zona"]["filas"]:
        assert Decimal(snap["zona"]["porcentaje_aplicado"]) == D(esp["zona"]["aplicado"])


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c["hoja"])
def test_computo_de_servicios(caso):
    r = computo(caso["computo"])
    esp = caso["esperado"]["computo"]
    assert r["antiguedad_final"] == esp["antiguedad_final"]
    for clave in ("total_servicios", "subtotal", "corresponde"):
        if clave in esp:
            assert list(r[clave]) == esp[clave], clave


@pytest.mark.parametrize("caso", [c for c in CASOS if c["zonas"]], ids=lambda c: c["hoja"])
def test_anexo_de_zona(caso):
    class Z:
        def __init__(self, z):
            from datetime import date
            self.dependencia, self.porcentaje_zona = z["dependencia"], D(z["porcentaje_zona"])
            self.fecha_desde, self.fecha_hasta = date.fromisoformat(z["fecha_desde"]), date.fromisoformat(z["fecha_hasta"])

    r = calcular_zona([Z(z) for z in caso["zonas"]], caso["causante"]["tipo_personal"])
    esp = caso["esperado"]["zona"]
    assert [f["porc_final"] for f in r["filas"]] == [D(x).quantize(Decimal("0.0001")) for x in esp["filas"]]
    assert r["total"] == D(esp["total"]).quantize(Decimal("0.0001"))
    assert r["porcentaje_aplicado"] == D(esp["aplicado"])


def test_zona_que_no_alcanza_el_minimo():
    from datetime import date

    class Z:
        dependencia, porcentaje_zona = "X", Decimal(10)
        fecha_desde, fecha_hasta = date(2020, 1, 1), date(2022, 6, 1)   # 2 años x 10% / 30 = 0,67% < 1%

    r = calcular_zona([Z()], "superior")
    assert not r["alcanza_minimo"] and r["porcentaje_aplicado"] == 0
