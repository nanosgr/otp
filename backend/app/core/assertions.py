"""Registro de *assertions* dinámicas para el motor RBAC.

Una assertion es un predicado con nombre `fn(user, context) -> bool` que se evalúa
en tiempo de request. Permite condicionar una regla de permiso a atributos del
recurso o del contexto (ownership, tenant, estado, horario, etc.) sin cablear la
lógica en cada endpoint.

Las reglas `role_permissions` referencian una assertion por nombre en la columna
`assertion`. Al chequear el permiso, `app.core.rbac.evaluate` resuelve el nombre
contra este registro y ejecuta el predicado con el `context` que provee el endpoint.

Para agregar una assertion de dominio, definirla en este módulo (o importarla desde
acá) decorada con `@register_assertion("nombre")`.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

# nombre -> predicado
AssertionFn = Callable[[Any, Dict[str, Any]], bool]
_REGISTRY: Dict[str, AssertionFn] = {}


def register_assertion(name: str) -> Callable[[AssertionFn], AssertionFn]:
    """Decorador para registrar un predicado bajo un nombre."""

    def decorator(fn: AssertionFn) -> AssertionFn:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_assertion(name: str) -> AssertionFn | None:
    return _REGISTRY.get(name)


def run_assertion(name: str, user: Any, context: Dict[str, Any] | None) -> bool:
    """Ejecuta la assertion `name`.

    Fail-closed: si el nombre no está registrado, retorna False (la regla
    condicional no otorga acceso).
    """
    fn = _REGISTRY.get(name)
    if fn is None:
        return False
    try:
        return bool(fn(user, context or {}))
    except Exception:
        return False


def registered_assertions() -> list[str]:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------------
# Assertions built-in
# ---------------------------------------------------------------------------

@register_assertion("owner")
def _owner(user: Any, context: Dict[str, Any]) -> bool:
    """El usuario es dueño del recurso.

    El endpoint debe pasar `context={"resource_owner_id": <id>}`.
    """
    owner_id = context.get("resource_owner_id")
    return owner_id is not None and owner_id == getattr(user, "id", None)
