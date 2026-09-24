"""Fragmentos de inserción de 1-2 líneas para los archivos compartidos.

Los artefactos grandes (modelo, service, router, migración, página, tipos) viven
en `templates/*.jinja`. Acá sólo lo chico, como f-strings, para evitar el
escaping de JSX en Jinja.
"""
from __future__ import annotations

from . import typemap
from .spec import ResourceField, Spec


# --------------------------------------------------------------------- backend


def crud_import(s: Spec) -> str:
    S = s.resource.singular_pascal
    return f"{S}, {S}Create, {S}Update,"


def crud_instance(s: Spec) -> str:
    return f"{s.resource.singular}_service = {s.resource.singular_pascal}Service()"


def api_init_import(s: Spec) -> str:
    return f"from app.api import {s.resource.plural}"


def api_init_include(s: Spec) -> str:
    p = s.resource.plural
    return f'api_router.include_router({p}.router, prefix="/{p}", tags=["{p}"])'


def env_import(s: Spec) -> str:
    return f"{s.resource.singular_pascal},"


def init_db_permissions(s: Spec) -> str:
    p = s.resource.plural
    lines = [f"# --- {p}: recurso generado por scripts/scaffold_resource.py ---"]
    for action in ("create", "read", "update", "delete"):
        lines.append(
            f'{{"name": "{p}:{action}", "description": "{action.capitalize()} {p}", '
            f'"resource": "{p}", "action": "{action}"}},'
        )
    return "\n".join(lines)


def deps_helpers(s: Spec) -> str:
    sg = s.resource.singular
    p = s.resource.plural
    out = []
    for action in ("read", "create", "update", "delete"):
        out.append(f"def require_{sg}_{action}():")
        out.append(f'    return require_permissions(["{p}:{action}"])')
        out.append("")
    return "\n".join(out).rstrip()


# -------------------------------------------------------------------- frontend


def app_import(s: Spec) -> str:
    P = s.resource.plural_pascal
    return f"import {P} from '@/pages/{P}';"


def app_route(s: Spec) -> str:
    P = s.resource.plural_pascal
    p = s.resource.plural
    return f'<Route path="/{p}" element={{<PrivateRoute><{P} /></PrivateRoute>}} />'


def services_type_import(s: Spec) -> str:
    S = s.resource.singular_pascal
    P = s.resource.plural_pascal
    return f"{S},\nCreate{S}DTO,\nUpdate{S}DTO,\nGet{P}Params,"


def services_object(s: Spec) -> str:
    """El objeto `<singular>Service` completo (f-string por el escaping de genéricos TS)."""
    S = s.resource.singular_pascal
    P = s.resource.plural_pascal
    p = s.resource.plural
    q = "buildQuery(params as Record<string, string | number | boolean | undefined>)"
    return "\n".join([
        f"// {S} Service (recurso generado)",
        f"export const {s.resource.singular}Service = {{",
        f"  getAll: (params: Get{P}Params = {{}}) =>",
        f"    apiClient.get<PaginatedResponse<{S}>>(`/{p}/${{{q}}}`),",
        "",
        "  getById: (id: number) =>",
        f"    apiClient.get<{S}>(`/{p}/${{id}}`),",
        "",
        f"  create: (data: Create{S}DTO) =>",
        f"    apiClient.post<{S}>('/{p}/', data),",
        "",
        f"  update: (id: number, data: Update{S}DTO) =>",
        f"    apiClient.put<{S}>(`/{p}/${{id}}`, data),",
        "",
        "  delete: (id: number) =>",
        f"    apiClient.delete<void>(`/{p}/${{id}}`),",
        "};",
    ])


def sidebar_icon(s: Spec) -> str:
    return f"{s.resource.icon},"


def sidebar_navitem(s: Spec) -> str:
    return (
        f"{{ label: '{s.resource.label_plural}', href: '/{s.resource.plural}', "
        f"icon: {s.resource.icon}, permissions: ['{s.resource.plural}:read'] }},"
    )


# ------------------------------------------------------------------------ docs


def claude_md_endpoints(s: Spec) -> str:
    p = s.resource.plural
    kind = "acceso con alcance de datos vía `require_scope`" if s.is_scoped else "CRUD por permiso plano"
    return f"- **{s.resource.label_plural}:** `/{p}/` ({kind}; recurso generado)"


def claude_md_schema(s: Spec) -> str:
    p = s.resource.plural
    if s.scoping.mode == "own":
        detail = "`owner_id` para `own`"
    elif s.scoping.mode == "attribute":
        detail = f"`{s.scoping.dimension}` para la dimensión `attribute`"
    else:
        detail = "recurso CRUD plano"
    return f"- `{p}` — recurso generado ({detail})"
