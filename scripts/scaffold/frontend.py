"""Genera los fragmentos TSX por-campo de la página (form inputs, columnas).

Devuelve strings sin indentar; la plantilla los coloca con `| indent(N)`.
"""
from __future__ import annotations

from .spec import ResourceField, Spec

_SELECT_CLS = (
    "w-full px-3 py-2 text-sm rounded-md border border-stone-200 dark:border-stone-700 "
    "bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100 focus:outline-none "
    "focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-colors"
)
_LABEL_CLS = "block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5"


def _label(f: ResourceField) -> str:
    base = f.name.replace("_", " ")
    base = base[:1].upper() + base[1:]
    return base + (" *" if not f.optional and f.type != "bool" else "")


def enum_const(spec: Spec, f: ResourceField) -> str:
    return f"{spec.resource.plural.upper()}_{f.name.upper()}_OPTIONS"


def enum_filter_const(spec: Spec, f: ResourceField) -> str:
    return f"{spec.resource.plural.upper()}_{f.name.upper()}_FILTER_OPTIONS"


def empty_form(spec: Spec) -> str:
    from . import typemap
    parts = [f"{f.name}: {typemap.ts_empty_value(f)}" for f in spec.fields]
    return "{ " + ", ".join(parts) + " }"


def form_field(spec: Spec, f: ResourceField) -> str:
    name = f.name
    if f.type == "bool":
        return (
            '<label className="flex items-center gap-2 cursor-pointer">\n'
            '  <input\n'
            '    type="checkbox"\n'
            f'    checked={{formData.{name}}}\n'
            f'    onChange={{(e) => setFormData({{ ...formData, {name}: e.target.checked }})}}\n'
            '    className="rounded accent-blue-600"\n'
            '  />\n'
            f'  <span className="text-sm font-medium text-stone-700 dark:text-stone-300">{_label(f)}</span>\n'
            '</label>'
        )
    if f.type == "enum":
        const = enum_const(spec, f)
        return (
            '<div>\n'
            f'  <label className="{_LABEL_CLS}">{_label(f)}</label>\n'
            '  <select\n'
            f'    value={{formData.{name}}}\n'
            f'    onChange={{(e) => setFormData({{ ...formData, {name}: e.target.value }})}}\n'
            f'    className="{_SELECT_CLS}"\n'
            '  >\n'
            f'    {{{const}.map((o) => (\n'
            '      <option key={o.value} value={o.value}>{o.label}</option>\n'
            '    ))}\n'
            '  </select>\n'
            '</div>'
        )
    if f.type == "text":
        return (
            '<div>\n'
            f'  <label className="{_LABEL_CLS}">{_label(f)}</label>\n'
            '  <textarea\n'
            f'    value={{formData.{name} ?? \'\'}}\n'
            f'    onChange={{(e) => setFormData({{ ...formData, {name}: e.target.value }})}}\n'
            '    rows={3}\n'
            f'    className="{_SELECT_CLS}"\n'
            '  />\n'
            '</div>'
        )
    if f.type in ("int", "float", "money"):
        return (
            '<Input\n'
            f'  label="{_label(f)}"\n'
            '  type="number"\n'
            f'  value={{formData.{name}}}\n'
            f'  onChange={{(e) => setFormData({{ ...formData, {name}: Number(e.target.value) }})}}\n'
            '/>'
        )
    # string
    req = "\n  required" if not f.optional else ""
    return (
        '<Input\n'
        f'  label="{_label(f)}"\n'
        f'  value={{formData.{name} ?? \'\'}}\n'
        f'  onChange={{(e) => setFormData({{ ...formData, {name}: e.target.value }})}}{req}\n'
        '/>'
    )


def column(spec: Spec, f: ResourceField) -> str:
    name = f.name
    label = f.name.replace("_", " ")
    label = label[:1].upper() + label[1:]
    if f.type == "money":
        body = (
            f"<span className=\"tabular-nums\">"
            f"{{o.{name}.toLocaleString('es-AR', {{ style: 'currency', currency: 'ARS' }})}}</span>"
        )
    elif f.type == "bool":
        body = f"<span className=\"text-xs\">{{o.{name} ? 'Sí' : 'No'}}</span>"
    elif f.type == "enum":
        const = enum_const(spec, f)
        body = (
            f'<span className="px-2 py-1 bg-stone-100 dark:bg-stone-800 text-stone-700 '
            f'dark:text-stone-300 text-xs rounded">'
            f'{{{const}.find((s) => s.value === o.{name})?.label ?? o.{name}}}</span>'
        )
    elif f.type == "text":
        body = f'<span className="text-stone-500 dark:text-stone-400 text-sm line-clamp-1">{{o.{name}}}</span>'
    else:
        body = f"<span>{{o.{name}}}</span>"
    return f"{{ key: '{name}', label: '{label}', render: (o) => {body} }},"


def columns_array(spec: Spec) -> str:
    lines = [
        "{ key: 'id', label: '#', render: (o) => "
        "<span className=\"font-mono text-xs text-stone-400\">#{o.id}</span> },"
    ]
    for f in spec.fields:
        lines.append(column(spec, f))
    if spec.has_owner:
        lines.append(
            "{ key: 'owner_id', label: 'Dueño', render: (o) => "
            "<span className=\"text-xs text-stone-500 dark:text-stone-400\">"
            "{o.owner_id === user?.id ? 'Yo' : o.owner_id ? `#${o.owner_id}` : '—'}</span> },"
        )
    return "\n".join(lines)


def form_body(spec: Spec) -> str:
    return "\n".join(form_field(spec, f) for f in spec.fields)


def required_string_check(spec: Spec) -> str:
    """Expresión JS que valida los strings requeridos (o '' si no hay)."""
    reqs = [f for f in spec.fields if f.type in ("string", "text") and not f.optional]
    if not reqs:
        return ""
    cond = " || ".join(f"!formData.{f.name}?.trim()" for f in reqs)
    names = ", ".join(_label_es(f) for f in reqs)
    return (
        f"if ({cond}) {{\n"
        f"      setFormError('Completá los campos obligatorios: {names}.');\n"
        f"      return;\n"
        f"    }}"
    )


def _label_es(f: ResourceField) -> str:
    base = f.name.replace("_", " ")
    return base[:1].upper() + base[1:]
