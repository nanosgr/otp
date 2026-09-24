"""Tests unitarios del generador de scaffold.

Correr desde la raíz del repo:  python -m pytest scripts/scaffold/tests -q
(requiere las deps dev: jinja2, pyyaml, pytest)
"""
import ast
import textwrap
from pathlib import Path

import pytest

from scripts.scaffold import blocks, domain_files, frontend
from scripts.scaffold.alembic_head import current_head
from scripts.scaffold.cli import build_insertions, find_repo_root
from scripts.scaffold.inserts import InsertionSet
from scripts.scaffold.render import build_context, make_env, new_revision_id
from scripts.scaffold.spec import Spec, load_spec, validate
from scripts.scaffold.strip import strip_marker_blocks

REPO = find_repo_root(Path(__file__))
SPEC_OWN = REPO / "scripts/scaffold/specs/examples/products.yaml"


def _spec_own() -> Spec:
    return load_spec(SPEC_OWN)


def _write_spec(tmp_path, body: str) -> Path:
    p = tmp_path / "s.yaml"
    p.write_text(textwrap.dedent(body))
    return p


# --------------------------------------------------------------------- alembic


def test_current_head_is_single():
    head = current_head(REPO)
    assert head and isinstance(head, str)


# ------------------------------------------------------------------------ spec


def test_spec_products_valid():
    errors, _ = validate(_spec_own())  # sin repo_root -> no chequea marcadores
    assert errors == []


def test_spec_rejects_reserved(tmp_path):
    spec = load_spec(_write_spec(tmp_path, """
        resource: { singular: user, plural: users }
        fields: [{ name: x, type: string }]
    """))
    errors, _ = validate(spec)
    assert any("reservado" in e for e in errors)


def test_spec_rejects_enum_without_values(tmp_path):
    spec = load_spec(_write_spec(tmp_path, """
        resource: { singular: item, plural: items }
        fields: [{ name: kind, type: enum }]
    """))
    errors, _ = validate(spec)
    assert any("enum_values" in e for e in errors)


def test_spec_attribute_adds_dimension_field(tmp_path):
    spec = load_spec(_write_spec(tmp_path, """
        resource: { singular: box, plural: boxes }
        fields: [{ name: label, type: string }]
        scoping: { mode: attribute, dimension: zone }
    """))
    assert any(f.name == "zone" and not f.optional for f in spec.fields)
    assert spec.has_owner and spec.is_scoped


# --------------------------------------------------------------------- inserts


def test_insertion_requires_unique_anchor(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("a = 1\nb = 2\na = 1\n")
    iset = InsertionSet(repo_root=tmp_path)
    iset.add_insertion("x.py", "a = 1", "z = 9", "after", "py", "T:X")
    with pytest.raises(ValueError):
        iset.render()


def test_insertion_roundtrip_is_identity(tmp_path):
    f = tmp_path / "x.py"
    original = "import os\n\n\nVALUE = 1\n"
    f.write_text(original)
    iset = InsertionSet(repo_root=tmp_path)
    iset.add_insertion("x.py", "VALUE = 1", "EXTRA = 2", "before", "py", "T:X")
    (_, new), = [(o, n) for o, n in iset.render().values()]
    assert "T:X:START" in new
    back, removed = strip_marker_blocks(new, "T:X")
    assert removed == 1
    assert back == original


# --------------------------------------------------------------- render / compile


@pytest.mark.parametrize("scope_mode", ["none", "own", "attribute"])
def test_generated_backend_is_valid_python(tmp_path, scope_mode):
    body = {
        "none": "scoping: { mode: none }",
        "own": "scoping: { mode: own }",
        "attribute": "scoping: { mode: attribute, dimension: zone }",
    }[scope_mode]
    spec = load_spec(_write_spec(tmp_path, f"""
        resource: {{ singular: widget, plural: widgets, icon: Box }}
        fields:
          - {{ name: title, type: string }}
          - {{ name: qty, type: int }}
          - {{ name: kind, type: enum, filterable: true, enum_values: [{{value: a, label: A}}, {{value: b, label: B}}] }}
        {body}
    """))
    assert validate(spec)[0] == []
    env = make_env()
    ctx = build_context(spec, head_rev="deadbeef", new_rev=new_revision_id())
    for tpl in ("backend/model_block.py.jinja", "backend/service_block.py.jinja",
                "backend/api_router.py.jinja", "backend/migration.py.jinja",
                "backend/test_resource.py.jinja"):
        ast.parse(env.get_template(tpl).render(**ctx))
    # deps helpers sólo aplica a non-scoped
    if not spec.is_scoped:
        ast.parse("def require_permissions(x):\n    pass\n" + blocks.deps_helpers(spec))


@pytest.mark.parametrize("mode", ["none", "own", "attribute"])
def test_build_insertions_produce_valid_python(tmp_path, mode):
    """Contra el árbol real: cada anchor resuelve y los .py editados parsean."""
    body = {
        "none": "scoping: { mode: none }",
        "own": "scoping: { mode: own }",
        "attribute": "scoping: { mode: attribute, dimension: zone }",
    }[mode]
    # sin campos filterable -> cubre la firma de count() sin `*`
    spec = load_spec(_write_spec(tmp_path, f"""
        resource: {{ singular: gadget, plural: gadgets, icon: Box }}
        fields:
          - {{ name: title, type: string }}
          - {{ name: qty, type: int }}
        {body}
    """))
    env = make_env()
    ctx = build_context(spec, head_rev=current_head(REPO), new_rev=new_revision_id())
    rendered = build_insertions(spec, REPO, ctx, env).render()
    assert len(rendered) > 10
    for path, (_old, new) in rendered.items():
        if path.suffix == ".py":
            ast.parse(new, filename=str(path))


# --------------------------------------------------------------- domain_files


def test_domain_files_consistent():
    spec = _spec_own()
    marks = domain_files.files_with_markers(spec)
    dels = domain_files.files_to_delete(spec, REPO)
    assert "backend/app/models/models.py" in marks
    assert f"backend/app/api/{spec.resource.plural}.py" in dels
    # un archivo no puede estar en las dos listas
    assert not (set(marks) & set(dels))
