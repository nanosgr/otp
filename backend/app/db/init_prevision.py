"""Seed idempotente de permisos y roles del dominio previsional."""
from sqlmodel import Session, select

from app.api.prevision import RECURSOS_DOMINIO
from app.models.models import Permission, Role, RolePermissionLink

ACCIONES = ("create", "read", "update", "delete")
CONFIG = {"conceptos", "grupos_concepto", "formulas_auxiliares", "concepto_vigencias", "tablas", "parametros"}
OPERATIVOS = set(RECURSOS_DOMINIO) - CONFIG

ROLES = {
    "Administrador": ("Administración completa del dominio previsional", lambda r, a: True),
    "Liquidador": (
        "Carga de causantes/beneficiarios y liquidaciones; lectura de reglas",
        lambda r, a: (r in OPERATIVOS and not (r == "liquidaciones" and a == "delete") and a != "delete") or (r in CONFIG and a == "read"),
    ),
    "Consulta": ("Solo lectura del dominio previsional", lambda r, a: a == "read"),
    "Auditor": ("Lectura del dominio y de la auditoría", lambda r, a: a == "read"),
}


def init_prevision(db: Session) -> None:
    perms = {}
    for resource in RECURSOS_DOMINIO:
        for action in ACCIONES:
            name = f"{resource}:{action}"
            p = db.exec(select(Permission).where(Permission.name == name)).first()
            if p is None:
                p = Permission(name=name, description=f"{action} {resource}", resource=resource, action=action)
                db.add(p)
            perms[(resource, action)] = p
    audit = db.exec(select(Permission).where(Permission.name == "audit:read")).first()
    db.commit()

    for name, (description, allowed) in ROLES.items():
        role = db.exec(select(Role).where(Role.name == name)).first()
        if role is None:
            role = Role(name=name, description=description)
            db.add(role)
            db.commit()
            db.refresh(role)
        wanted = [p for (r, a), p in perms.items() if allowed(r, a)]
        if name == "Auditor" and audit is not None:
            wanted.append(audit)
        for p in wanted:
            if db.get(RolePermissionLink, (role.id, p.id)) is None:
                db.add(RolePermissionLink(role_id=role.id, permission_id=p.id))
    # Admin y Manager de la plantilla heredan el dominio
    for name, allowed in (("Admin", lambda r, a: True), ("Manager", lambda r, a: a in ("read", "update"))):
        role = db.exec(select(Role).where(Role.name == name)).first()
        if role is None:
            continue
        for (r, a), p in perms.items():
            if allowed(r, a) and db.get(RolePermissionLink, (role.id, p.id)) is None:
                db.add(RolePermissionLink(role_id=role.id, permission_id=p.id))
    db.commit()
