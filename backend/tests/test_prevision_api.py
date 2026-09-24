"""Tests de los CRUD del dominio previsional (SQLite in-memory + TestClient)."""
import pytest
from fastapi.testclient import TestClient

from app.core import rbac
from app.core.security import create_access_token, get_password_hash
from app.db.database import get_db
from app.db.init_prevision import init_prevision
from app.main import app
from app.models.models import Role, User


@pytest.fixture(autouse=True)
def _clear_cache():
    rbac.invalidate_policy_cache()
    yield
    rbac.invalidate_policy_cache()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _user(db, name, role_name):
    role = db.query(Role).filter(Role.name == role_name).first()
    u = User(username=name, email=f"{name}@e.com", hashed_password=get_password_hash("x"))
    u.roles.append(role)
    db.add(u)
    db.commit()
    db.refresh(u)
    tok = create_access_token({"sub": u.username, "token_version": u.token_version})
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def headers(db):
    init_prevision(db)
    return {
        "admin": _user(db, "adm", "Administrador"),
        "liq": _user(db, "liq", "Liquidador"),
        "consulta": _user(db, "con", "Consulta"),
    }


CAUSANTE = {"dni": "20111222", "apellido": "Pérez", "nombre": "Juan", "tipo_personal": "superior"}


def test_causante_crud_y_filtros(client, headers):
    h = headers["admin"]
    r = client.post("/api/v1/causantes/", json=CAUSANTE, headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]

    b = client.post("/api/v1/beneficiarios/", headers=h, json={
        "causante_id": cid, "apellido": "Pérez", "nombre": "Ana", "parentesco": "conyuge", "porcentaje": "50.5"})
    assert b.status_code == 201, b.text

    lst = client.get(f"/api/v1/beneficiarios/?causante_id={cid}", headers=h).json()
    assert lst["total"] == 1 and lst["items"][0]["parentesco"] == "conyuge"

    assert client.get("/api/v1/causantes/?search=rez", headers=h).json()["total"] == 1

    up = client.put(f"/api/v1/causantes/{cid}", json={"nombre": "Juana"}, headers=h)
    assert up.status_code == 200 and up.json()["nombre"] == "Juana"

    # cascada al borrar el causante
    assert client.delete(f"/api/v1/causantes/{cid}", headers=h).status_code == 204
    assert client.get(f"/api/v1/causantes/{cid}", headers=h).status_code == 404


def test_validaciones(client, headers):
    h = headers["admin"]
    assert client.post("/api/v1/causantes/", headers=h, json={**CAUSANTE, "tipo_personal": "x"}).status_code == 422
    cid = client.post("/api/v1/causantes/", json=CAUSANTE, headers=h).json()["id"]
    r = client.put(f"/api/v1/causantes/{cid}", json={"tipo_personal": "x"}, headers=h)
    assert r.status_code == 422
    assert client.post("/api/v1/cargos/", headers=h, json={"causante_id": cid, "clase": 99}).status_code == 422


def test_permisos_por_rol(client, headers):
    assert client.get("/api/v1/causantes/", headers=headers["consulta"]).status_code == 200
    assert client.post("/api/v1/causantes/", json=CAUSANTE, headers=headers["consulta"]).status_code == 403
    assert client.post("/api/v1/causantes/", json=CAUSANTE, headers=headers["liq"]).status_code == 201
    # el liquidador lee pero no modifica conceptos
    assert client.get("/api/v1/conceptos/", headers=headers["liq"]).status_code == 200
    body = {"codigo": "10", "descripcion": "Clase"}
    assert client.post("/api/v1/conceptos/", json=body, headers=headers["liq"]).status_code == 403
    assert client.post("/api/v1/conceptos/", json=body, headers=headers["admin"]).status_code == 201


def test_concepto_codigo_unico(client, headers):
    h = headers["admin"]
    body = {"codigo": "10", "descripcion": "Clase"}
    assert client.post("/api/v1/conceptos/", json=body, headers=h).status_code == 201
    assert client.post("/api/v1/conceptos/", json=body, headers=h).status_code == 409


def test_tabla_con_filas_json(client, headers):
    h = headers["admin"]
    t = client.post("/api/v1/tablas/", headers=h, json={
        "codigo": "PORC_RETIRO_25", "columnas": [{"nombre": "ANIOS", "tipo": "int"}, {"nombre": "PORC", "tipo": "decimal"}]}).json()
    f = client.post("/api/v1/filas/", headers=h, json={"tabla_id": t["id"], "orden": 1, "valores": [10, "30"]})
    assert f.status_code == 201 and f.json()["valores"] == [10, "30"]


def test_liquidacion_cerrada_es_inmutable(client, headers):
    h = headers["admin"]
    cid = client.post("/api/v1/causantes/", json=CAUSANTE, headers=h).json()["id"]
    liq = client.post("/api/v1/liquidaciones/", headers=h, json={"causante_id": cid, "periodo": "2025-03", "tipo": "retiro"}).json()
    assert client.post("/api/v1/liquidaciones/", headers=h, json={"causante_id": cid, "periodo": "2025-13"}).status_code == 422
    rec = client.post("/api/v1/recibos/", headers=h, json={"liquidacion_id": liq["id"]}).json()

    assert client.put(f"/api/v1/liquidaciones/{liq['id']}", json={"estado": "CERRADA"}, headers=h).status_code == 200
    assert client.put(f"/api/v1/liquidaciones/{liq['id']}", json={"observaciones": "x"}, headers=h).status_code == 409
    assert client.delete(f"/api/v1/recibos/{rec['id']}", headers=h).status_code == 409


# ---- validación de fórmulas con el motor Rust (se omite si el wheel no está instalado) ----
from app.services import motor  # noqa: E402

requiere_motor = pytest.mark.skipif(motor._engine is None, reason="otp_engine no instalado")


def _concepto(codigo, importe, **extra):
    return {"codigo": codigo, "descripcion": codigo, "formula_importe": importe, **extra}


@requiere_motor
def test_concepto_con_sintaxis_invalida_se_rechaza(client, headers):
    h = headers["admin"]
    r = client.post("/api/v1/conceptos/", json=_concepto("10", "1 +"), headers=h)
    assert r.status_code == 422 and "sintaxis" in r.text
    assert client.post("/api/v1/conceptos/", json=_concepto("10", "FOO(1)"), headers=h).status_code == 422
    assert client.post("/api/v1/conceptos/", json=_concepto("10", "100 * 2%"), headers=h).status_code == 201


@requiere_motor
def test_dependencia_circular_se_rechaza_al_guardar(client, headers):
    h = headers["admin"]
    a = client.post("/api/v1/conceptos/", json=_concepto("A", "10"), headers=h).json()
    assert client.post("/api/v1/conceptos/", json=_concepto("B", "#A + 1"), headers=h).status_code == 201
    r = client.put(f"/api/v1/conceptos/{a['id']}", json={"formula_importe": "#B + 1"}, headers=h)
    assert r.status_code == 422 and "circular" in r.text
    # el concepto A no cambió
    assert client.get(f"/api/v1/conceptos/{a['id']}", headers=h).json()["formula_importe"] == "10"


@requiere_motor
def test_endpoint_validar_formula_usa_auxiliares(client, headers):
    h = headers["admin"]
    assert client.post("/api/v1/formulas/validar", json={"formula": "IVA(100)"}, headers=h).status_code == 422
    client.post("/api/v1/formulas-auxiliares/", json={"codigo": "IVA", "formato": "(x)", "formula": "? * 21%"}, headers=h)
    r = client.post("/api/v1/formulas/validar", json={"formula": "IVA(#10) + CLASE"}, headers=h)
    assert r.status_code == 200 and r.json()["conceptos"] == ["10"] and "CLASE" in r.json()["variables"]
