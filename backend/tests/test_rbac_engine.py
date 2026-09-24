"""Tests del motor de decisión RBAC (app.core.rbac).

Espeja los escenarios de `simple-rbac/tests/test_acl.py`: jerarquía de roles,
reglas DENY con precedencia, wildcards, assertions y resultado ternario.
"""
from types import SimpleNamespace

import pytest

from app.core import rbac
from app.core.assertions import register_assertion
from app.core.rbac import EffectivePolicy, evaluate, pattern_matches, resolve_role_family


# ---------------------------------------------------------------------------
# helpers: roles/usuarios duck-typed (sin ORM)
# ---------------------------------------------------------------------------

def role(rid, *, parents=(), is_active=True):
    return SimpleNamespace(id=rid, is_active=is_active, parents=list(parents))


def user(*roles, is_superuser=False):
    return SimpleNamespace(id=1, is_superuser=is_superuser, roles=list(roles))


# ---------------------------------------------------------------------------
# pattern_matches / wildcards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pattern,resource,action,expected", [
    ("users:read", "users", "read", True),
    ("users:read", "users", "update", False),
    ("users:*", "users", "delete", True),
    ("*:read", "reports", "read", True),
    ("*:read", "reports", "export", False),
    ("*:*", "anything", "whatever", True),
    ("users:read", "roles", "read", False),
])
def test_pattern_matches(pattern, resource, action, expected):
    assert pattern_matches(pattern, resource, action) is expected


# ---------------------------------------------------------------------------
# evaluate: ternario
# ---------------------------------------------------------------------------

def test_evaluate_ternario():
    policy = EffectivePolicy(allow={"users:read"}, deny={"users:delete"})
    assert evaluate(policy, "users", "read") is True
    assert evaluate(policy, "users", "delete") is False
    assert evaluate(policy, "users", "update") is None  # sin regla


def test_deny_gana_sobre_allow():
    policy = EffectivePolicy(allow={"reports:export"}, deny={"reports:*"})
    assert evaluate(policy, "reports", "export") is False


def test_wildcard_allow():
    policy = EffectivePolicy(allow={"users:*"})
    assert evaluate(policy, "users", "read") is True
    assert evaluate(policy, "users", "delete") is True
    assert evaluate(policy, "roles", "read") is None


# ---------------------------------------------------------------------------
# assertions / allow condicional
# ---------------------------------------------------------------------------

def test_assertion_condicional():
    policy = EffectivePolicy(conditional=[("users:read", "owner")])
    u = SimpleNamespace(id=7)
    assert evaluate(policy, "users", "read", user=u, context={"resource_owner_id": 7}) is True
    assert evaluate(policy, "users", "read", user=u, context={"resource_owner_id": 99}) is None
    assert evaluate(policy, "users", "read", user=u, context=None) is None


def test_assertion_desconocida_fail_closed():
    policy = EffectivePolicy(conditional=[("users:read", "no_existe")])
    assert evaluate(policy, "users", "read", user=SimpleNamespace(id=1), context={}) is None


def test_assertion_custom_registrada():
    @register_assertion("in_region")
    def _in_region(u, ctx):
        return getattr(u, "region", None) == ctx.get("region")

    policy = EffectivePolicy(conditional=[("reports:read", "in_region")])
    u = SimpleNamespace(id=1, region="LATAM")
    assert evaluate(policy, "reports", "read", user=u, context={"region": "LATAM"}) is True
    assert evaluate(policy, "reports", "read", user=u, context={"region": "EU"}) is None


def test_deny_gana_sobre_assertion():
    policy = EffectivePolicy(deny={"users:read"}, conditional=[("users:read", "owner")])
    u = SimpleNamespace(id=5)
    assert evaluate(policy, "users", "read", user=u, context={"resource_owner_id": 5}) is False


# ---------------------------------------------------------------------------
# resolve_role_family: jerarquía
# ---------------------------------------------------------------------------

def test_familia_transitiva():
    grandpa = role(1)
    parent = role(2, parents=[grandpa])
    child = role(3, parents=[parent])
    ids = {r.id for r in resolve_role_family(child)}
    assert ids == {1, 2, 3}


def test_familia_diamante_sin_duplicar():
    top = role(1)
    left = role(2, parents=[top])
    right = role(3, parents=[top])
    bottom = role(4, parents=[left, right])
    assert sorted(r.id for r in resolve_role_family(bottom)) == [1, 2, 3, 4]


def test_familia_con_ciclo_no_recursa_infinito():
    a = role(1)
    b = role(2, parents=[a])
    a.parents = [b]  # ciclo artificial
    ids = {r.id for r in resolve_role_family(a)}
    assert ids == {1, 2}


def test_effective_role_ids_ignora_inactivos():
    inactive_parent = role(1, is_active=False)
    active = role(2, parents=[inactive_parent])
    assert rbac.effective_role_ids(user(active)) == {2}


# ---------------------------------------------------------------------------
# build_policy end-to-end sobre SQLite (jerarquía + deny + assertion + wildcard)
# ---------------------------------------------------------------------------

def _seed(db):
    from app.models.models import Permission, Role, RoleParentLink, RolePermissionLink, User

    perms = {
        name: Permission(name=name, resource=name.split(":")[0], action=name.split(":")[1])
        for name in ["users:read", "users:delete", "audit:read", "*:read", "reports:export"]
    }
    for p in perms.values():
        db.add(p)
    db.commit()
    for p in perms.values():
        db.refresh(p)

    base = Role(name="Base")
    mid = Role(name="Mid")
    top = Role(name="Top")
    db.add_all([base, mid, top])
    db.commit()
    db.refresh(base); db.refresh(mid); db.refresh(top)

    # jerarquía: top -> mid -> base
    db.add(RoleParentLink(role_id=mid.id, parent_id=base.id))
    db.add(RoleParentLink(role_id=top.id, parent_id=mid.id))

    # base: lectura de todo vía wildcard, pero DENY explícito de audit:read
    db.add(RolePermissionLink(role_id=base.id, permission_id=perms["*:read"].id))
    db.add(RolePermissionLink(role_id=base.id, permission_id=perms["audit:read"].id, effect="deny"))
    # mid: users:delete condicionado a owner
    db.add(RolePermissionLink(role_id=mid.id, permission_id=perms["users:delete"].id, assertion="owner"))
    # top: export de reports
    db.add(RolePermissionLink(role_id=top.id, permission_id=perms["reports:export"].id))
    db.commit()

    u = User(username="u", email="u@e.com", hashed_password="x")
    u.roles.append(top)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_build_policy_end_to_end(db):
    u = _seed(db)
    policy = rbac.build_policy(db, u)

    # hereda wildcard de lectura desde Base
    assert rbac.evaluate(policy, "reports", "read") is True
    # DENY heredado gana sobre el wildcard
    assert rbac.evaluate(policy, "audit", "read") is False
    # permiso propio de Top
    assert rbac.evaluate(policy, "reports", "export") is True
    # regla condicional heredada de Mid
    assert rbac.evaluate(policy, "users", "delete", user=u, context={"resource_owner_id": u.id}) is True
    assert rbac.evaluate(policy, "users", "delete", user=u, context={"resource_owner_id": 999}) is None
    # sin regla
    assert rbac.evaluate(policy, "settings", "update") is None


def test_build_policy_superuser(db):
    from app.models.models import User

    u = User(username="su", email="su@e.com", hashed_password="x", is_superuser=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    policy = rbac.build_policy(db, u)
    assert rbac.evaluate(policy, "anything", "whatever") is True
