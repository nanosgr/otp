from sqlmodel import Session, select
from app.db.database import engine
from app.models.models import User, Role, Permission, RolePermissionLink, UserScope
from app.core.security import get_password_hash
from app.db.init_prevision import init_prevision


def _ensure_link(db, role_id, permission_id, *, effect="allow", assertion=None,
                 scope="all", scope_dimension=None):
    """Crea (idempotente) una regla role->permission con effect/assertion/scope."""
    link = db.get(RolePermissionLink, (role_id, permission_id))
    if link is None:
        db.add(RolePermissionLink(
            role_id=role_id, permission_id=permission_id,
            effect=effect, assertion=assertion,
            scope=scope, scope_dimension=scope_dimension,
        ))


def init_db():
    with Session(engine) as db:
        try:
            permissions_data = [
                {"name": "users:create", "description": "Create users", "resource": "users", "action": "create"},
                {"name": "users:read", "description": "Read users", "resource": "users", "action": "read"},
                {"name": "users:update", "description": "Update users", "resource": "users", "action": "update"},
                {"name": "users:delete", "description": "Delete users", "resource": "users", "action": "delete"},
                {"name": "roles:create", "description": "Create roles", "resource": "roles", "action": "create"},
                {"name": "roles:read", "description": "Read roles", "resource": "roles", "action": "read"},
                {"name": "roles:update", "description": "Update roles", "resource": "roles", "action": "update"},
                {"name": "roles:delete", "description": "Delete roles", "resource": "roles", "action": "delete"},
                {"name": "permissions:create", "description": "Create permissions", "resource": "permissions", "action": "create"},
                {"name": "permissions:read", "description": "Read permissions", "resource": "permissions", "action": "read"},
                {"name": "permissions:update", "description": "Update permissions", "resource": "permissions", "action": "update"},
                {"name": "permissions:delete", "description": "Delete permissions", "resource": "permissions", "action": "delete"},
                {"name": "dashboard:read", "description": "Access dashboard", "resource": "dashboard", "action": "read"},
                {"name": "reports:read", "description": "View reports", "resource": "reports", "action": "read"},
                {"name": "reports:export", "description": "Export reports", "resource": "reports", "action": "export"},
                {"name": "settings:read", "description": "View settings", "resource": "settings", "action": "read"},
                {"name": "settings:update", "description": "Update settings", "resource": "settings", "action": "update"},
                {"name": "audit:read", "description": "View audit logs", "resource": "audit", "action": "read"},
                # --- wildcards (demostración del matching resource/action con `*`) ---
                {"name": "*:*", "description": "Full access (wildcard)", "resource": "*", "action": "*"},
                {"name": "*:read", "description": "Read any resource (wildcard)", "resource": "*", "action": "read"},
            ]

            permissions = []
            for perm_data in permissions_data:
                existing = db.exec(select(Permission).where(Permission.name == perm_data["name"])).first()
                if not existing:
                    permission = Permission(**perm_data)
                    db.add(permission)
                    permissions.append(permission)
                else:
                    permissions.append(existing)

            db.commit()
            for p in permissions:
                db.refresh(p)

            by_name = {p.name: p for p in permissions}
            # permisos "concretos" (sin wildcards) para los grants enumerados
            concrete = [p for p in permissions if p.resource != "*"]

            roles_data = [
                {"name": "Super Admin", "description": "Full system access"},
                {"name": "Admin", "description": "Administrative access"},
                {"name": "Manager", "description": "Management access"},
                {"name": "User", "description": "Basic user access"},
                {"name": "Viewer", "description": "Read-only access"},
            ]

            roles = []
            for role_data in roles_data:
                existing = db.exec(select(Role).where(Role.name == role_data["name"])).first()
                if not existing:
                    role = Role(**role_data)
                    db.add(role)
                    roles.append(role)
                else:
                    roles.append(existing)

            db.commit()
            for r in roles:
                db.refresh(r)

            by_role = {r.name: r for r in roles}
            super_admin = by_role.get("Super Admin")
            admin = by_role.get("Admin")
            manager = by_role.get("Manager")
            user_role = by_role.get("User")
            viewer = by_role.get("Viewer")

            if roles and permissions:
                # Super Admin: una sola regla wildcard `*:*`
                if super_admin and not super_admin.permissions:
                    super_admin.permissions = [by_name["*:*"]]

                # Admin: todo lo concreto salvo permissions:delete
                if admin and not admin.permissions:
                    admin.permissions = [p for p in concrete if not (p.resource == "permissions" and p.action == "delete")]

                # Manager: lecturas/updates concretos + users:create
                if manager and not manager.permissions:
                    manager.permissions = [p for p in concrete if p.action in ["read", "update"] or (p.resource == "users" and p.action == "create")]

                # User: dashboard/reports de lectura
                if user_role and not user_role.permissions:
                    user_role.permissions = [p for p in concrete if p.action == "read" and p.resource in ["dashboard", "reports"]]

                # Viewer: lectura de cualquier recurso vía wildcard `*:read`
                if viewer and not viewer.permissions:
                    viewer.permissions = [by_name["*:read"]]

                db.commit()

                # --- Regla DENY: Viewer NO puede leer auditoría, pese al wildcard `*:read` ---
                if viewer and "audit:read" in by_name:
                    _ensure_link(db, viewer.id, by_name["audit:read"].id, effect="deny")

                # --- Regla con ASSERTION: User puede leer su propio registro de usuario ---
                if user_role and "users:read" in by_name:
                    _ensure_link(db, user_role.id, by_name["users:read"].id, assertion="owner")

                # --- Jerarquía de roles: Admin -> Manager -> User ---
                if admin and manager and not admin.parents:
                    admin.parents = [manager]
                if manager and user_role and not manager.parents:
                    manager.parents = [user_role]

                db.commit()


            users_data = [
                {"username": "superadmin", "email": "superadmin@example.com", "full_name": "Super Administrator", "password": "admin123", "is_superuser": True, "role_name": "Super Admin"},
                {"username": "admin", "email": "admin@example.com", "full_name": "Administrator", "password": "admin123", "is_superuser": False, "role_name": "Admin"},
                {"username": "manager", "email": "manager@example.com", "full_name": "Manager User", "password": "manager123", "is_superuser": False, "role_name": "Manager"},
                {"username": "user", "email": "user@example.com", "full_name": "Regular User", "password": "user123", "is_superuser": False, "role_name": "User"},
            ]

            for user_data in users_data:
                existing = db.exec(select(User).where(User.username == user_data["username"])).first()
                if not existing:
                    role_name = user_data.pop("role_name")
                    password = user_data.pop("password")
                    user = User(**user_data, hashed_password=get_password_hash(password))
                    role = db.exec(select(Role).where(Role.name == role_name)).first()
                    if role:
                        user.roles.append(role)
                    db.add(user)

            db.commit()

            init_prevision(db)

            print("Base de datos inicializada correctamente!")

            print("\n=== Usuarios creados ===")
            for user in db.exec(select(User)).all():
                roles_names = [r.name for r in user.roles]
                print(f"Usuario: {user.username} | Email: {user.email} | Roles: {', '.join(roles_names)}")

        except Exception as e:
            print(f"Error inicializando la base de datos: {e}")
            db.rollback()


if __name__ == "__main__":
    print("Inicializando datos...")
    init_db()
