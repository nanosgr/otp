"""Entorno Jinja + armado del contexto de plantillas.

Delimitadores custom (`<< >>` para variables) para no chocar con JSX `{ }` ni
template strings `${ }` en las plantillas `.tsx`.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import frontend, typemap
from .spec import Spec

TEMPLATES_DIR = Path(__file__).parent / "templates"


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        variable_start_string="<<", variable_end_string=">>",
        block_start_string="{%", block_end_string="%}",
        comment_start_string="{#", comment_end_string="#}",
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    env.filters["repr"] = repr
    return env


def new_revision_id() -> str:
    return secrets.token_hex(6)


def build_context(spec: Spec, *, head_rev: str, new_rev: str) -> dict:
    r = spec.resource
    return {
        "singular": r.singular,
        "plural": r.plural,
        "S": r.singular_pascal,
        "PluralPascal": r.plural_pascal,
        "label_singular": r.label_singular,
        "label_plural": r.label_plural,
        "icon": r.icon,
        "tag": spec.marker_tag,
        "fields": spec.fields,
        "enum_fields": spec.enum_fields,
        "filter_fields": spec.filter_fields,
        "string_fields": spec.string_fields,
        "required_string_fields": spec.required_string_fields,
        "scoping": spec.scoping,
        "is_scoped": spec.is_scoped,
        "has_owner": spec.has_owner,
        "scope_mode": spec.scoping.mode,
        "dimension": spec.scoping.dimension,
        "variant": spec.variant,
        "grants": spec.grants,
        "frontend": spec.frontend,
        "docs": spec.docs,
        "head_rev": head_rev,
        "new_rev": new_rev,
        "create_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "tm": typemap,
        "sample_create": {f.name: _sample_value(f) for f in spec.fields},
        "sample_update": {
            f.name: _sample_value(f, alt=True)
            for f in spec.fields if f.type in ("string", "text", "enum")
        } or {spec.fields[0].name: _sample_value(spec.fields[0], alt=True)},
        "dim_value": (
            _sample_value(next(f for f in spec.fields if f.name == spec.scoping.dimension))
            if spec.scoping.mode == "attribute" else None
        ),
        "audit_after": ", ".join(f'"{f.name}": result.{f.name}' for f in spec.fields),
        "audit_before": ", ".join(f'"{f.name}": obj.{f.name}' for f in spec.fields),
        "filter_kwargs": "".join(f", {f.name}={f.name}" for f in spec.filter_fields),
        "filter_params_sig": "".join(
            f", {f.name}: {typemap.py_query_annot(f)} = None" for f in spec.filter_fields
        ),
        # fragmentos TSX pre-renderizados para la página
        "columns_src": frontend.columns_array(spec),
        "form_body_src": frontend.form_body(spec),
        "empty_form_src": frontend.empty_form(spec),
        "form_pick_src": ", ".join(f"{f.name}: item.{f.name}" for f in spec.fields),
        "required_check_src": frontend.required_string_check(spec),
        "filter_enum_fields": [f for f in spec.filter_fields if f.type == "enum"],
        "enum_consts": [
            {
                "field": f.name,
                "options": frontend.enum_const(spec, f),
                "filter": frontend.enum_filter_const(spec, f),
                "filterable": f.filterable,
            }
            for f in spec.enum_fields
        ],
    }


def _sample_value(f, *, alt: bool = False):
    if f.type in ("string", "text"):
        return f"{f.name} {'editado' if alt else 'demo'}"
    if f.type == "int":
        return 7 if alt else 3
    if f.type in ("float", "money"):
        return 99.0 if alt else 12.5
    if f.type == "bool":
        return alt is False
    if f.type == "enum":
        vals = [e.value for e in f.enum_values]
        return vals[-1] if (alt and len(vals) > 1) else vals[0]
    return "x"


def render(env: Environment, template: str, context: dict) -> str:
    return env.get_template(template).render(**context)


def snippets(env: Environment, context: dict):
    """Módulo con las macros de `snippets.jinja` ya ligadas al contexto."""
    return env.get_template("snippets.jinja").make_module(context)
