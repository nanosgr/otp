"""Tests de integración de la jerarquía de roles y reglas de efecto vía la API.

Usan SQLite in-memory + TestClient con override de `get_db`.
"""
import pytest
from fastapi.testclient import TestClient

from app.core import rbac
from app.core.security import create_access_token
from app.db.database import get_db
from app.main import app
from app.models.models import Permission, Role, RoleParentLink, RolePermissionLink, User
from app.services.crud import user_service


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


def _token(user: User) -> dict:
    tok = create_access_token({"sub": user.username, "token_version": user.token_version})
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def graph(db):
    perms = {
        n: Permission(name=n, resource=n.split(":")[0], action=n.split(":")[1])
        for n in ["users:read", "roles:read", "audit:read", "*:read"]
    }
    db.add_all(perms.values())
    db.commit()
    for p in perms.values():
        db.refresh(p)

    base = Role(name="Base")     # roles:read
    lead = Role(name="Lead")     # hereda de Base
    viewer = Role(name="Viewer")  # *:read pero DENY audit:read
    db.add_all([base, lead, viewer])
    db.commit()
    for r in (base, lead, viewer):
        db.refresh(r)

    db.add(RolePermissionLink(role_id=base.id, permission_id=perms["roles:read"].id))
    db.add(RoleParentLink(role_id=lead.id, parent_id=base.id))
    db.add(RolePermissionLink(role_id=viewer.id, permission_id=perms["*:read"].id))
    db.add(RolePermissionLink(role_id=viewer.id, permission_id=perms["audit:read"].id, effect="deny"))
    db.commit()

    def mkuser(name, role):
        u = User(username=name, email=f"{name}@e.com", hashed_password="x")
        u.roles.append(role)
        db.add(u)
        db.commit()
        db.refresh(u)
        return user_service.get_user(db, u.id)

    return {
        "base": base, "lead": lead, "viewer": viewer, "perms": perms,
        "u_lead": mkuser("lead_user", lead),
        "u_viewer": mkuser("viewer_user", viewer),
    }


def test_hierarchy_grants_inherited_permission(client, graph):
    # 'Lead' no tiene roles:read directo, lo hereda de 'Base'
    r = client.get("/api/v1/roles/", headers=_token(graph["u_lead"]))
    assert r.status_code == 200


def test_deny_overrides_wildcard(client, graph):
    # 'Viewer' tiene *:read pero DENY audit:read
    r = client.get("/api/v1/audit/logs", headers=_token(graph["u_viewer"]))
    assert r.status_code == 403


def test_wildcard_allows_other_reads(client, graph):
    r = client.get("/api/v1/roles/", headers=_token(graph["u_viewer"]))
    assert r.status_code == 200


@pytest.fixture
def superuser(db):
    su = User(username="root", email="root@e.com", hashed_password="x", is_superuser=True)
    db.add(su)
    db.commit()
    db.refresh(su)
    return su


def test_assign_parents_cycle_returns_400(client, graph, superuser):
    lead, base = graph["lead"], graph["base"]
    body = {"role_id": base.id, "parent_ids": [lead.id]}  # base -> lead crea ciclo (lead ya -> base)
    r = client.post(f"/api/v1/roles/{base.id}/parents", json=body, headers=_token(superuser))
    assert r.status_code == 400
    assert "cycle" in r.json()["detail"].lower()


def test_effective_permissions_endpoint(client, graph, superuser):
    r = client.get(f"/api/v1/roles/{graph['lead'].id}/effective-permissions", headers=_token(superuser))
    assert r.status_code == 200
    data = r.json()
    assert "roles:read" in data["allow"]
    assert set(data["contributing_role_ids"]) == {graph["lead"].id, graph["base"].id}
