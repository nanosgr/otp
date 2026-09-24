"""Modelo del spec YAML + carga + validación.

Un spec describe un recurso CRUD nuevo. Ejemplo mínimo:

    resource:
      singular: product
      plural: products
    fields:
      - { name: name, type: string }
      - { name: price, type: money }

Los campos `singular_pascal`, `plural_pascal`, `label_singular`, `label_plural` e
`icon` se derivan si no se dan.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit(
        "Falta PyYAML. Instalá las dependencias dev:\n"
        "  cd backend && ./venv/bin/pip install -r requirements-dev.txt"
    )

# Tipos soportados hoy. `date` / `datetime` quedan para una fase posterior
# (widgets de fecha en el form + import condicional en models.py).
FIELD_TYPES = {
    "string", "text", "int", "float", "money", "bool", "enum",
}
SCOPING_MODES = {"none", "own", "attribute"}
FRONTEND_VARIANTS = {"auto", "plain", "scoped"}

# Recursos ya usados por el core RBAC — no se pueden pisar.
RESERVED_RESOURCES = {
    "users", "roles", "permissions", "audit", "auth", "password",
    "dashboard", "reports", "settings",
}

_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# Subconjunto de exports de lucide-react 1.8 usados como iconos de recurso.
# Sólo para un warning "quizá no exista"; no es exhaustivo ni bloqueante.
KNOWN_LUCIDE_ICONS = {
    "Box", "Package", "ShoppingCart", "ShoppingBag", "Tag", "Tags", "Truck",
    "Warehouse", "Boxes", "ClipboardList", "Clipboard", "FileText", "Files",
    "Folder", "FolderOpen", "Archive", "Layers", "List", "Grid", "Table",
    "Receipt", "CreditCard", "DollarSign", "Wallet", "Banknote", "Coins",
    "Users", "User", "Building", "Building2", "Store", "Factory", "Home",
    "Calendar", "CalendarDays", "Clock", "Bell", "Mail", "MessageSquare",
    "Ticket", "Bookmark", "Star", "Heart", "Flag", "MapPin", "Map", "Globe",
    "Settings", "Wrench", "Tool", "Cog", "Database", "Server", "HardDrive",
    "Book", "BookOpen", "Library", "GraduationCap", "Briefcase", "Award",
    "Car", "Plane", "Ship", "Bike", "Package2", "PackageCheck", "PackageOpen",
    "Barcode", "QrCode", "Scan", "Boxes", "Container", "Palette", "Image",
}


@dataclass
class EnumValue:
    value: str
    label: str


@dataclass
class ResourceField:
    """Un campo de negocio del modelo (no incluye id/timestamps/owner_id)."""
    name: str
    type: str
    optional: bool = False
    default: Any = None
    filterable: bool = False
    enum_values: list[EnumValue] = field(default_factory=list)
    # marca los campos que el generador agrega solo (ej. la dimensión de scope)
    synthetic: bool = False


@dataclass
class Scoping:
    mode: str = "none"
    dimension: str | None = None


@dataclass
class Grants:
    rely_on_auto_inherit: bool = True
    explicit: list = field(default_factory=list)
    scoped_demo_roles: bool = False


@dataclass
class FrontendCfg:
    generate: bool = True
    variant: str = "auto"


@dataclass
class DocsCfg:
    update_claude_md: bool = True


@dataclass
class ResourceMeta:
    singular: str
    plural: str
    singular_pascal: str
    plural_pascal: str
    label_singular: str
    label_plural: str
    icon: str


@dataclass
class Spec:
    resource: ResourceMeta
    fields: list[ResourceField]
    scoping: Scoping
    grants: Grants
    frontend: FrontendCfg
    docs: DocsCfg
    source_path: Path | None = None

    # ------------------------------------------------------------------ derived

    @property
    def marker_tag(self) -> str:
        """Etiqueta del marcador centinela, ej. `TEMPLATE:PRODUCTS`."""
        return f"TEMPLATE:{self.resource.plural.upper()}"

    @property
    def is_scoped(self) -> bool:
        return self.scoping.mode != "none"

    @property
    def has_owner(self) -> bool:
        return self.scoping.mode in ("own", "attribute")

    @property
    def variant(self) -> str:
        if self.frontend.variant != "auto":
            return self.frontend.variant
        return "scoped" if self.is_scoped else "plain"

    @property
    def enum_fields(self) -> list[ResourceField]:
        return [f for f in self.fields if f.type == "enum"]

    @property
    def filter_fields(self) -> list[ResourceField]:
        return [f for f in self.fields if f.filterable]

    @property
    def string_fields(self) -> list[ResourceField]:
        return [f for f in self.fields if f.type in ("string", "text")]

    @property
    def required_string_fields(self) -> list[ResourceField]:
        return [f for f in self.string_fields if not f.optional]


# --------------------------------------------------------------------------- io


def _pascal(snake: str) -> str:
    return "".join(part.capitalize() for part in snake.split("_") if part)


def _humanize(snake: str) -> str:
    words = snake.replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else words


def load_spec(path: str | Path) -> Spec:
    """Carga y normaliza un spec YAML. No valida (usar `validate`)."""
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    r = raw.get("resource", {}) or {}
    singular = str(r.get("singular", "")).strip()
    plural = str(r.get("plural", "")).strip()

    meta = ResourceMeta(
        singular=singular,
        plural=plural,
        singular_pascal=r.get("singular_pascal") or _pascal(singular),
        plural_pascal=r.get("plural_pascal") or _pascal(plural),
        label_singular=r.get("label_singular") or _humanize(singular),
        label_plural=r.get("label_plural") or _humanize(plural),
        icon=r.get("icon") or "Box",
    )

    fields: list[ResourceField] = []
    for fr in raw.get("fields", []) or []:
        evs = [
            EnumValue(value=str(e["value"]), label=str(e.get("label", e["value"])))
            for e in (fr.get("enum_values") or [])
        ]
        fields.append(ResourceField(
            name=str(fr["name"]).strip(),
            type=str(fr.get("type", "string")).strip(),
            optional=bool(fr.get("optional", False)),
            default=fr.get("default"),
            filterable=bool(fr.get("filterable", False)),
            enum_values=evs,
        ))

    sc = raw.get("scoping", {}) or {}
    scoping = Scoping(
        mode=str(sc.get("mode", "none")).strip(),
        dimension=(str(sc["dimension"]).strip() if sc.get("dimension") else None),
    )

    gr = raw.get("grants", {}) or {}
    grants = Grants(
        rely_on_auto_inherit=bool(gr.get("rely_on_auto_inherit", True)),
        explicit=list(gr.get("explicit", []) or []),
        scoped_demo_roles=bool(gr.get("scoped_demo_roles", False)),
    )

    fe = raw.get("frontend", {}) or {}
    frontend = FrontendCfg(
        generate=bool(fe.get("generate", True)),
        variant=str(fe.get("variant", "auto")).strip(),
    )

    dc = raw.get("docs", {}) or {}
    docs = DocsCfg(update_claude_md=bool(dc.get("update_claude_md", True)))

    spec = Spec(
        resource=meta, fields=fields, scoping=scoping,
        grants=grants, frontend=frontend, docs=docs, source_path=path,
    )

    # La dimensión de scope="attribute" es un campo de negocio requerido:
    # el usuario elige el valor al crear/editar la fila (como `warehouse` en orders).
    if scoping.mode == "attribute" and scoping.dimension:
        if not any(f.name == scoping.dimension for f in spec.fields):
            spec.fields.append(ResourceField(
                name=scoping.dimension, type="string", optional=False,
                filterable=True, synthetic=True,
            ))

    return spec


# --------------------------------------------------------------------- validate


def validate(spec: Spec, repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    """Devuelve `(errores, warnings)`. Vacío de errores == spec válido."""
    errors: list[str] = []
    warnings: list[str] = []
    m = spec.resource

    for label, value in (("singular", m.singular), ("plural", m.plural)):
        if not value:
            errors.append(f"resource.{label} es obligatorio")
        elif not _IDENT_RE.match(value):
            errors.append(f"resource.{label} debe ser snake_case ([a-z][a-z0-9_]*): {value!r}")

    if m.singular and m.singular == m.plural:
        errors.append("resource.singular y resource.plural no pueden ser iguales")

    if m.plural in RESERVED_RESOURCES or m.singular in RESERVED_RESOURCES:
        errors.append(
            f"el recurso choca con un recurso reservado del core RBAC "
            f"({sorted(RESERVED_RESOURCES)})"
        )

    if not spec.fields:
        errors.append("se requiere al menos un campo en `fields`")

    seen: set[str] = set()
    for f in spec.fields:
        if not _IDENT_RE.match(f.name or ""):
            errors.append(f"field.name inválido (snake_case): {f.name!r}")
        if f.name in seen:
            errors.append(f"field.name duplicado: {f.name!r}")
        seen.add(f.name)
        if f.name in ("id", "owner_id", "created_at", "updated_at"):
            errors.append(f"field.name {f.name!r} es estructural, no lo declares")
        if f.type not in FIELD_TYPES:
            errors.append(f"field {f.name!r}: tipo desconocido {f.type!r} (válidos: {sorted(FIELD_TYPES)})")
        if f.type == "enum":
            if not f.enum_values:
                errors.append(f"field {f.name!r}: enum requiere enum_values")
            values = {e.value for e in f.enum_values}
            if f.default is not None and str(f.default) not in values:
                errors.append(
                    f"field {f.name!r}: default {f.default!r} no está en enum_values {sorted(values)}"
                )

    if spec.scoping.mode not in SCOPING_MODES:
        errors.append(f"scoping.mode inválido: {spec.scoping.mode!r} (válidos: {sorted(SCOPING_MODES)})")
    if spec.scoping.mode == "attribute" and not spec.scoping.dimension:
        errors.append("scoping.mode == 'attribute' requiere scoping.dimension")
    if spec.scoping.dimension and not _IDENT_RE.match(spec.scoping.dimension):
        errors.append(f"scoping.dimension debe ser snake_case: {spec.scoping.dimension!r}")

    if spec.frontend.variant not in FRONTEND_VARIANTS:
        errors.append(f"frontend.variant inválido: {spec.frontend.variant!r}")

    if spec.grants.scoped_demo_roles:
        warnings.append(
            "grants.scoped_demo_roles todavía no está implementado y se ignora; "
            "Admin/Manager igual heredan el recurso automáticamente. Agregá roles "
            "con scope a mano en init_db.py si necesitás un demo tipo Vendedor."
        )

    if m.icon and m.icon not in KNOWN_LUCIDE_ICONS:
        warnings.append(
            f"icono {m.icon!r} no está en la lista conocida de lucide-react; "
            f"verificá que exista (https://lucide.dev/icons)"
        )

    if repo_root is not None and (m.singular or m.plural):
        hits = _existing_marker_files(repo_root, spec.marker_tag)
        if hits:
            errors.append(
                f"el recurso {m.plural!r} ya fue scaffoldeado (marcadores {spec.marker_tag} en "
                f"{', '.join(hits[:3])}{'…' if len(hits) > 3 else ''}). "
                f"Corré `python scripts/remove_domain.py {m.plural}` primero."
            )

    return errors, warnings


def _existing_marker_files(repo_root: Path, tag: str) -> list[str]:
    hits: list[str] = []
    for sub in ("backend/app", "frontend/src", "scripts/scaffold/specs"):
        base = repo_root / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in (".py", ".ts", ".tsx", ".yaml", ".yml", ".md"):
                try:
                    if f"{tag}:" in p.read_text(encoding="utf-8"):
                        hits.append(str(p.relative_to(repo_root)))
                except (UnicodeDecodeError, OSError):
                    pass
    return hits
