from sqlmodel import Session, select, func, or_
from sqlalchemy import select as sa_select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.models.models import (
    User, Role, Permission, RolePermissionLink, RoleParentLink, UserScope,
    UserCreate, UserUpdate, RoleCreate, RoleUpdate, PermissionCreate, PermissionUpdate,
)
from app.core.security import get_password_hash, verify_password
from app.core import rbac


class UserService:
    def get_user(self, db: Session, user_id: int) -> Optional[User]:
        stmt = sa_select(User).options(selectinload(User.roles).selectinload(Role.permissions)).where(User.id == user_id)
        return db.execute(stmt).scalars().first()

    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        return db.exec(select(User).where(User.username == username)).first()

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.exec(select(User).where(User.email == email)).first()

    def get_users(self, db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None, is_active: Optional[bool] = None) -> List[User]:
        stmt = sa_select(User).options(selectinload(User.roles).selectinload(Role.permissions))
        if search:
            stmt = stmt.where(or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            ))
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        return list(db.execute(stmt.offset(skip).limit(limit)).scalars().unique().all())

    def count_users(self, db: Session, search: Optional[str] = None, is_active: Optional[bool] = None) -> int:
        query = select(func.count(User.id))
        if search:
            query = query.where(or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            ))
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        return db.exec(query).one()

    def create_user(self, db: Session, user: UserCreate, created_by: Optional[int] = None) -> User:
        db_user = User(
            username=user.username,
            email=user.email,
            hashed_password=get_password_hash(user.password),
            full_name=user.full_name,
            is_active=user.is_active,
            created_by=created_by,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def update_user(self, db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
        db_user = self.get_user(db, user_id)
        if db_user:
            update_data = user_update.model_dump(exclude_unset=True)
            if "password" in update_data:
                update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
            if update_data.get("is_active") is False:
                db_user.token_version += 1
            for field, value in update_data.items():
                setattr(db_user, field, value)
            db.commit()
            db.refresh(db_user)
        return db_user

    def delete_user(self, db: Session, user_id: int) -> bool:
        db_user = self.get_user(db, user_id)
        if db_user:
            db.delete(db_user)
            db.commit()
            return True
        return False

    def authenticate_user(self, db: Session, username: str, password: str) -> Optional[User]:
        user = self.get_user_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def change_password(self, db: Session, user_id: int, current_password: str, new_password: str) -> bool:
        db_user = self.get_user(db, user_id)
        if not db_user or not verify_password(current_password, db_user.hashed_password):
            return False
        db_user.hashed_password = get_password_hash(new_password)
        db.commit()
        return True

    def increment_token_version(self, db: Session, user_id: int) -> None:
        db_user = db.get(User, user_id)
        if db_user:
            db_user.token_version += 1
            db.commit()

    def assign_roles_to_user(self, db: Session, user_id: int, role_ids: List[int]) -> Optional[User]:
        db_user = self.get_user(db, user_id)
        if db_user:
            roles = db.exec(select(Role).where(Role.id.in_(role_ids))).all()
            db_user.roles = roles
            db_user.token_version += 1
            db.commit()
        return self.get_user(db, user_id)


class RoleService:
    def get_role(self, db: Session, role_id: int) -> Optional[Role]:
        stmt = (
            sa_select(Role)
            .options(selectinload(Role.permissions), selectinload(Role.parents))
            .where(Role.id == role_id)
        )
        return db.execute(stmt).scalars().first()

    def get_role_by_name(self, db: Session, name: str) -> Optional[Role]:
        return db.exec(select(Role).where(Role.name == name)).first()

    def get_roles(self, db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None, is_active: Optional[bool] = None) -> List[Role]:
        stmt = sa_select(Role).options(selectinload(Role.permissions), selectinload(Role.parents))
        if search:
            stmt = stmt.where(or_(
                Role.name.ilike(f"%{search}%"),
                Role.description.ilike(f"%{search}%"),
            ))
        if is_active is not None:
            stmt = stmt.where(Role.is_active == is_active)
        return list(db.execute(stmt.offset(skip).limit(limit)).scalars().unique().all())

    def count_roles(self, db: Session, search: Optional[str] = None, is_active: Optional[bool] = None) -> int:
        query = select(func.count(Role.id))
        if search:
            query = query.where(or_(
                Role.name.ilike(f"%{search}%"),
                Role.description.ilike(f"%{search}%"),
            ))
        if is_active is not None:
            query = query.where(Role.is_active == is_active)
        return db.exec(query).one()

    def create_role(self, db: Session, role: RoleCreate) -> Role:
        db_role = Role(**role.model_dump())
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role

    def update_role(self, db: Session, role_id: int, role_update: RoleUpdate) -> Optional[Role]:
        db_role = self.get_role(db, role_id)
        if db_role:
            update_data = role_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_role, field, value)
            db.commit()
            db.refresh(db_role)
            if "is_active" in update_data:
                rbac.invalidate_policy_cache()
        return db_role

    def delete_role(self, db: Session, role_id: int) -> bool:
        db_role = self.get_role(db, role_id)
        if db_role:
            # limpiar filas de jerarquía que referencian a este rol como padre o hijo
            for link in db.exec(
                select(RoleParentLink).where(
                    or_(RoleParentLink.role_id == role_id, RoleParentLink.parent_id == role_id)
                )
            ).all():
                db.delete(link)
            db.delete(db_role)
            db.commit()
            rbac.invalidate_policy_cache()
            return True
        return False

    def assign_permissions_to_role(self, db: Session, role_id: int, rules) -> Optional[Role]:
        """Reemplaza las reglas rol->permiso. `rules` es una lista de objetos con
        `permission_id`, `effect` ("allow"/"deny"), `assertion` opcional y
        `scope` ("all"/"own"/"attribute") con `scope_dimension` opcional.

        Lanza ValueError si `scope == "attribute"` sin `scope_dimension`.
        """
        db_role = self.get_role(db, role_id)
        if not db_role:
            return None

        rules = list(rules or [])
        wanted_ids = {r.permission_id for r in rules}
        valid_ids = set(
            db.exec(select(Permission.id).where(Permission.id.in_(wanted_ids))).all()
        ) if wanted_ids else set()

        # Normalizar + validar antes de tocar la DB (falla limpio con ValueError).
        normalized = []
        for r in rules:
            if r.permission_id not in valid_ids:
                continue
            effect = (getattr(r, "effect", None) or "allow").lower()
            scope = (getattr(r, "scope", None) or "all").lower()
            if scope not in ("all", "own", "attribute"):
                scope = "all"
            dimension = getattr(r, "scope_dimension", None) or None
            if scope == "attribute" and not dimension:
                raise ValueError("scope_dimension is required when scope is 'attribute'")
            normalized.append((
                r.permission_id,
                effect if effect in ("allow", "deny") else "allow",
                getattr(r, "assertion", None) or None,
                scope,
                dimension if scope == "attribute" else None,
            ))

        for link in db.exec(
            select(RolePermissionLink).where(RolePermissionLink.role_id == role_id)
        ).all():
            db.delete(link)
        db.flush()

        for permission_id, effect, assertion, scope, dimension in normalized:
            db.add(RolePermissionLink(
                role_id=role_id,
                permission_id=permission_id,
                effect=effect,
                assertion=assertion,
                scope=scope,
                scope_dimension=dimension,
            ))
        db.commit()
        rbac.invalidate_policy_cache()
        return self.get_role(db, role_id)

    # ------------------------------------------------------------------
    # Jerarquía de roles
    # ------------------------------------------------------------------

    def _ancestor_ids(self, db: Session, role_id: int) -> set:
        """IDs de todos los ancestros de `role_id` (cycle-safe)."""
        seen: set = set()
        stack = [role_id]
        while stack:
            current = stack.pop()
            for parent_id in db.exec(
                select(RoleParentLink.parent_id).where(RoleParentLink.role_id == current)
            ).all():
                if parent_id not in seen:
                    seen.add(parent_id)
                    stack.append(parent_id)
        return seen

    def would_create_cycle(self, db: Session, role_id: int, parent_id: int) -> bool:
        if role_id == parent_id:
            return True
        # ciclo si role_id ya es ancestro de parent_id
        return role_id in self._ancestor_ids(db, parent_id) or role_id == parent_id

    def assign_parents_to_role(self, db: Session, role_id: int, parent_ids: List[int]) -> Optional[Role]:
        db_role = self.get_role(db, role_id)
        if not db_role:
            return None

        parent_ids = list(dict.fromkeys(parent_ids))  # dedup preservando orden
        existing_ids = set(
            db.exec(select(Role.id).where(Role.id.in_(parent_ids))).all()
        ) if parent_ids else set()

        for pid in parent_ids:
            if pid not in existing_ids:
                raise ValueError(f"Parent role {pid} does not exist")
            if self.would_create_cycle(db, role_id, pid):
                raise ValueError(f"Assigning parent {pid} would create a cycle")

        for link in db.exec(
            select(RoleParentLink).where(RoleParentLink.role_id == role_id)
        ).all():
            db.delete(link)
        db.flush()

        for pid in parent_ids:
            db.add(RoleParentLink(role_id=role_id, parent_id=pid))
        db.commit()
        rbac.invalidate_policy_cache()
        return self.get_role(db, role_id)

    def get_role_rules(self, db: Session, role_id: int) -> Optional[list]:
        """Reglas directas del rol (sin resolver jerarquía) — para prefilar la UI."""
        if self.get_role(db, role_id) is None:
            return None
        rows = db.exec(
            select(RolePermissionLink).where(RolePermissionLink.role_id == role_id)
        ).all()
        return [
            {
                "permission_id": r.permission_id,
                "effect": r.effect,
                "assertion": r.assertion,
                "scope": getattr(r, "scope", "all") or "all",
                "scope_dimension": r.scope_dimension,
            }
            for r in rows
        ]

    def get_effective_permissions(self, db: Session, role_id: int) -> Optional[dict]:
        """Devuelve las reglas efectivas del rol resueltas sobre su jerarquía."""
        db_role = self.get_role(db, role_id)
        if not db_role:
            return None
        family = list(rbac.resolve_role_family(db_role))
        contributing = [r.id for r in family if r.is_active and r.id is not None]
        allow: set = set()
        deny: set = set()
        conditional: list = []
        scoped: list = []
        if contributing:
            rows = db.exec(
                select(RolePermissionLink, Permission)
                .join(Permission, Permission.id == RolePermissionLink.permission_id)
                .where(RolePermissionLink.role_id.in_(contributing))
                .where(Permission.is_active == True)  # noqa: E712
            ).all()
            for link, perm in rows:
                pattern = f"{perm.resource}:{perm.action}"
                if link.assertion:
                    conditional.append({"pattern": pattern, "assertion": link.assertion})
                elif link.effect == "deny":
                    deny.add(pattern)
                elif getattr(link, "scope", "all") not in (None, "", "all"):
                    scoped.append({
                        "pattern": pattern,
                        "scope": link.scope,
                        "dimension": link.scope_dimension,
                    })
                else:
                    allow.add(pattern)
        return {
            "role_id": role_id,
            "contributing_role_ids": contributing,
            "allow": sorted(allow),
            "deny": sorted(deny),
            "conditional": conditional,
            "scoped": scoped,
        }


class PermissionService:
    def get_permission(self, db: Session, permission_id: int) -> Optional[Permission]:
        return db.get(Permission, permission_id)

    def get_permission_by_name(self, db: Session, name: str) -> Optional[Permission]:
        return db.exec(select(Permission).where(Permission.name == name)).first()

    def get_permissions(self, db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None, is_active: Optional[bool] = None, resource: Optional[str] = None, action: Optional[str] = None) -> List[Permission]:
        query = select(Permission)
        if search:
            query = query.where(or_(
                Permission.name.ilike(f"%{search}%"),
                Permission.description.ilike(f"%{search}%"),
            ))
        if is_active is not None:
            query = query.where(Permission.is_active == is_active)
        if resource:
            query = query.where(Permission.resource == resource)
        if action:
            query = query.where(Permission.action == action)
        return db.exec(query.offset(skip).limit(limit)).all()

    def count_permissions(self, db: Session, search: Optional[str] = None, is_active: Optional[bool] = None, resource: Optional[str] = None, action: Optional[str] = None) -> int:
        query = select(func.count(Permission.id))
        if search:
            query = query.where(or_(
                Permission.name.ilike(f"%{search}%"),
                Permission.description.ilike(f"%{search}%"),
            ))
        if is_active is not None:
            query = query.where(Permission.is_active == is_active)
        if resource:
            query = query.where(Permission.resource == resource)
        if action:
            query = query.where(Permission.action == action)
        return db.exec(query).one()

    def create_permission(self, db: Session, permission: PermissionCreate) -> Permission:
        db_permission = Permission(**permission.model_dump())
        db.add(db_permission)
        db.commit()
        db.refresh(db_permission)
        return db_permission

    def update_permission(self, db: Session, permission_id: int, permission_update: PermissionUpdate) -> Optional[Permission]:
        db_permission = self.get_permission(db, permission_id)
        if db_permission:
            update_data = permission_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_permission, field, value)
            db.commit()
            db.refresh(db_permission)
            rbac.invalidate_policy_cache()
        return db_permission

    def delete_permission(self, db: Session, permission_id: int) -> bool:
        db_permission = self.get_permission(db, permission_id)
        if db_permission:
            for link in db.exec(
                select(RolePermissionLink).where(RolePermissionLink.permission_id == permission_id)
            ).all():
                db.delete(link)
            db.delete(db_permission)
            db.commit()
            rbac.invalidate_policy_cache()
            return True
        return False


class UserScopeService:
    """Valores de alcance por usuario (tabla user_scopes)."""

    def list_for_user(self, db: Session, user_id: int) -> List[UserScope]:
        return list(db.exec(select(UserScope).where(UserScope.user_id == user_id)).all())

    def replace_for_user(self, db: Session, user_id: int, items) -> List[UserScope]:
        """Reemplaza el set completo de scopes del usuario. `items` = objetos con
        `dimension` y `value`."""
        for sc in db.exec(select(UserScope).where(UserScope.user_id == user_id)).all():
            db.delete(sc)
        db.flush()
        seen = set()
        for it in items or []:
            dimension = (getattr(it, "dimension", None) or "").strip()
            value = str(getattr(it, "value", "") or "").strip()
            if not dimension or not value:
                continue
            key = (dimension, value)
            if key in seen:
                continue
            seen.add(key)
            db.add(UserScope(user_id=user_id, dimension=dimension, value=value))
        db.commit()
        rbac.invalidate_policy_cache()
        return self.list_for_user(db, user_id)


user_service = UserService()
role_service = RoleService()
permission_service = PermissionService()
user_scope_service = UserScopeService()
