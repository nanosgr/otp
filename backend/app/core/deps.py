from collections import namedtuple
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session
from typing import List, Optional
from app.db.database import get_db
from app.core.security import verify_token
from app.core import rbac
from app.services.crud import user_service
from app.models.models import User

security = HTTPBearer()

# Re-export para compatibilidad / uso desde servicios y endpoints
invalidate_policy_cache = rbac.invalidate_policy_cache


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise credentials_exception

    # La clave de cache incluye token_version: si el token fue revocado, hay miss.
    cache_key = (payload["sub"], payload["token_version"])
    cached = rbac._policy_cache.get(cache_key)

    if cached is not None:
        user_id, _ = cached
        user = user_service.get_user(db, user_id)
        if user is None:
            raise credentials_exception
        return user

    user = user_service.get_user_by_username(db, username=payload["sub"])
    if user is None:
        raise credentials_exception

    if user.token_version != payload["token_version"]:
        raise credentials_exception

    rbac.get_cached_policy(db, user)
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def _split(permission: str) -> tuple:
    resource, _, action = permission.partition(":")
    return resource, action


def require_permissions(required_permissions: List[str]):
    """Dependencia estática: exige (AND) cada permiso `resource:action`.

    Evalúa sin contexto, por lo que las reglas condicionadas por assertion NO
    otorgan acceso acá; para eso usar `has_permission()` dentro del endpoint.
    """

    def permission_checker(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ):
        policy = rbac.get_cached_policy(db, current_user)
        for required in required_permissions:
            resource, action = _split(required)
            if rbac.evaluate(policy, resource, action) is not True:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied. Required: {required}",
                )
        return current_user

    return permission_checker


def has_permission(
    current_user: User,
    resource: str,
    action: str,
    *,
    db: Session,
    context: Optional[dict] = None,
) -> bool:
    """Evaluación completa (incluye wildcards, DENY y assertions con contexto)."""
    policy = rbac.get_cached_policy(db, current_user)
    return rbac.evaluate(policy, resource, action, user=current_user, context=context) is True


# Valor que devuelve `require_scope`: el usuario + su alcance de datos resuelto.
ScopedAccess = namedtuple("ScopedAccess", ["user", "scope"])


def require_scope(resource: str, action: str):
    """Dependencia para endpoints con alcance de datos ("¿sobre qué filas?").

    Otorga si hay un `allow` (todas), una regla `scope` (`own`/`attribute`) o el
    wildcard del superusuario; deniega (403) sólo si hay `deny` o ninguna regla.
    El endpoint debe aplicar el `Scope` resultante: `access.scope.apply(stmt, Model)`
    en listados y `access.scope.matches(row)` sobre una fila cargada.
    """

    def scope_dep(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db),
    ) -> ScopedAccess:
        policy = rbac.get_cached_policy(db, current_user)
        scope = rbac.resolve_scope(policy, resource, action, current_user)
        if scope.denied or not scope.granted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {resource}:{action}",
            )
        return ScopedAccess(current_user, scope)

    return scope_dep


def check_owner_or_permission(
    resource_owner_id: Optional[int],
    current_user: User,
    permission: str,
    *,
    db: Optional[Session] = None,
) -> bool:
    """DEPRECADO: usar `has_permission(..., context={"resource_owner_id": ...})`.

    True si el usuario tiene el permiso (con la assertion `owner` resuelta contra
    `resource_owner_id`) o si es el dueño del recurso.
    """
    resource, action = _split(permission)
    context = {"resource_owner_id": resource_owner_id}
    if db is not None:
        policy = rbac.get_cached_policy(db, current_user)
    else:
        cached = rbac._policy_cache.get(rbac.cache_key(current_user))
        policy = cached[1] if cached else rbac.EffectivePolicy()
    if rbac.evaluate(policy, resource, action, user=current_user, context=context) is True:
        return True
    return resource_owner_id is not None and current_user.id == resource_owner_id


def require_user_read():
    return require_permissions(["users:read"])

def require_user_create():
    return require_permissions(["users:create"])

def require_user_update():
    return require_permissions(["users:update"])

def require_user_delete():
    return require_permissions(["users:delete"])

def require_role_read():
    return require_permissions(["roles:read"])

def require_role_create():
    return require_permissions(["roles:create"])

def require_role_update():
    return require_permissions(["roles:update"])

def require_role_delete():
    return require_permissions(["roles:delete"])

def require_permission_read():
    return require_permissions(["permissions:read"])

def require_permission_create():
    return require_permissions(["permissions:create"])

def require_permission_update():
    return require_permissions(["permissions:update"])

def require_permission_delete():
    return require_permissions(["permissions:delete"])
