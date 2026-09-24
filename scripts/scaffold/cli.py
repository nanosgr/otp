"""CLI del generador de scaffold de recursos."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import blocks, domain_files
from .alembic_head import current_head
from .inserts import InsertionSet
from .render import build_context, make_env, new_revision_id, render
from .spec import Spec, load_spec, validate


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for cand in [here, *here.parents]:
        if (cand / "backend").is_dir() and (cand / "frontend").is_dir():
            return cand
    raise SystemExit("No encuentro la raíz del repo (esperaba backend/ y frontend/).")


def _post_run_block(spec: Spec) -> str:
    p = spec.resource.plural
    lines = [
        "",
        "=" * 70,
        "SIGUIENTES PASOS",
        "=" * 70,
        "1. Revisar el diff:            git diff",
        "2. Aplicar la migración:       cd backend && ./venv/bin/alembic upgrade head",
        '3. Re-seed:                    cd backend && ./venv/bin/python -c '
        '"from app.db.init_db import create_tables, init_db; create_tables(); init_db()"',
        "4. Tests backend:              cd backend && ./venv/bin/pytest",
    ]
    if spec.frontend.generate:
        lines.append("5. Gate de tipos frontend:     cd frontend && npm run build")
    lines += [
        f'6. Opcional: agregar "{p}" a get_available_resources() en '
        "backend/app/api/permissions.py",
        f"7. Smoke: uvicorn + npm run dev  ->  /{p}",
        "",
        f"Para deshacer:  python scripts/remove_domain.py {p}",
    ]
    return "\n".join(lines)


def build_insertions(spec: Spec, repo_root: Path, ctx: dict, env) -> InsertionSet:
    iset = InsertionSet(repo_root=repo_root)
    tag = spec.marker_tag
    S = spec.resource.singular_pascal
    p = spec.resource.plural
    P = spec.resource.plural_pascal

    # -------------------------------------------------------------- archivos nuevos
    iset.add_file(f"backend/app/api/{p}.py", render(env, "backend/api_router.py.jinja", ctx))
    iset.add_file(
        f"backend/alembic/versions/{ctx['new_rev']}_add_{p}.py",
        render(env, "backend/migration.py.jinja", ctx),
    )
    iset.add_file(f"backend/tests/test_{p}.py", render(env, "backend/test_resource.py.jinja", ctx))

    canonical_spec = repo_root / domain_files.spec_rel_path(spec)
    if not spec.source_path or spec.source_path.resolve() != canonical_spec.resolve():
        iset.add_file(domain_files.spec_rel_path(spec),
                      (spec.source_path or Path()).read_text(encoding="utf-8")
                      if spec.source_path else "")

    if spec.frontend.generate:
        iset.add_file(f"frontend/src/pages/{P}.tsx", render(env, "frontend/page.tsx.jinja", ctx))

    # ---------------------------------------------------------------- backend edits
    iset.add_insertion(
        "backend/app/models/models.py", "# Resolver referencias circulares",
        render(env, "backend/model_block.py.jinja", ctx), "before", "py", tag,
    )
    iset.add_insertion(
        "backend/app/services/crud.py",
        "    UserCreate, UserUpdate, RoleCreate, RoleUpdate, PermissionCreate, PermissionUpdate,",
        blocks.crud_import(spec), "after", "py", tag, spaced=False,
    )
    iset.add_insertion(
        "backend/app/services/crud.py", "user_service = UserService()",
        render(env, "backend/service_block.py.jinja", ctx), "before", "py", tag,
    )
    iset.add_insertion(
        "backend/app/services/crud.py", "user_scope_service = UserScopeService()",
        blocks.crud_instance(spec), "after", "py", tag, spaced=False,
    )
    iset.add_insertion(
        "backend/app/api/__init__.py",
        "from app.api import auth, users, roles, permissions, audit, password_reset",
        blocks.api_init_import(spec), "after", "py", tag, spaced=False,
    )
    iset.add_insertion(
        "backend/app/api/__init__.py",
        'api_router.include_router(audit.router, prefix="/audit", tags=["audit"])',
        blocks.api_init_include(spec), "after", "py", tag, spaced=False,
    )
    iset.add_insertion(
        "backend/app/db/init_db.py",
        "# --- wildcards (demostración del matching resource/action con",
        blocks.init_db_permissions(spec), "before", "py", tag, spaced=False,
    )
    iset.add_insertion(
        "backend/alembic/env.py", "    UserScope,",
        blocks.env_import(spec), "after", "py", tag, spaced=False,
    )
    if not spec.is_scoped:
        iset.add_insertion(
            "backend/app/core/deps.py",
            '    return require_permissions(["permissions:delete"])',
            blocks.deps_helpers(spec), "after", "py", tag, indent="",
        )

    # --------------------------------------------------------------- frontend edits
    if spec.frontend.generate:
        iset.add_insertion(
            "frontend/src/App.tsx", "import Permissions from '@/pages/Permissions';",
            blocks.app_import(spec), "after", "ts", tag, spaced=False,
        )
        iset.add_insertion(
            "frontend/src/App.tsx",
            '<Route path="/permissions" element={<PrivateRoute><Permissions /></PrivateRoute>} />',
            blocks.app_route(spec), "after", "jsx", tag, spaced=False,
        )
        iset.add_insertion(
            "frontend/src/lib/api/services.ts", "} from '@/types';",
            blocks.services_type_import(spec), "before", "ts", tag,
            indent="  ", spaced=False,
        )
        iset.add_insertion(
            "frontend/src/lib/api/services.ts", "// Audit Service",
            blocks.services_object(spec), "before", "ts", tag,
        )
        iset.add_insertion(
            "frontend/src/types/index.ts", "// AuditLog types",
            render(env, "frontend/types_block.ts.jinja", ctx), "before", "ts", tag,
        )
        if spec.enum_fields:
            iset.add_insertion(
                "frontend/src/lib/constants.ts", "",
                render(env, "frontend/constants_block.ts.jinja", ctx),
                "append_eof", "ts", tag,
            )
        iset.add_insertion(
            "frontend/src/components/layout/Sidebar.tsx", "  Key,",
            blocks.sidebar_icon(spec), "after", "ts", tag, spaced=False,
        )
        iset.add_insertion(
            "frontend/src/components/layout/Sidebar.tsx",
            "{ label: 'Permisos',   href: '/permissions', icon: Key,    permissions: ['permissions:read'] },",
            blocks.sidebar_navitem(spec), "after", "ts", tag, spaced=False,
        )

    # -------------------------------------------------------------------- docs
    if spec.docs.update_claude_md:
        iset.add_insertion(
            "CLAUDE.md", "- **Permissions:** `/permissions/` (CRUD)",
            blocks.claude_md_endpoints(spec), "after", "md", tag, spaced=False,
        )
        iset.add_insertion(
            "CLAUDE.md", "- Users → scope values (`user_scopes`: `user_id, dimension, value`)",
            blocks.claude_md_schema(spec), "after", "md", tag, spaced=False,
        )

    return iset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scaffold_resource",
        description="Genera un recurso CRUD nuevo (backend + frontend) a partir de un spec YAML.",
    )
    parser.add_argument("--from", dest="spec", help="ruta al spec YAML")
    parser.add_argument("--dry-run", action="store_true", help="muestra los cambios sin escribir")
    parser.add_argument("--no-frontend", action="store_true", help="no genera la parte de frontend")
    parser.add_argument("--no-docs", action="store_true", help="no toca CLAUDE.md")
    parser.add_argument("--interactive", action="store_true", help="(no implementado aún)")
    args = parser.parse_args(argv)

    if args.interactive:
        print("El modo --interactive todavía no está implementado. Usá --from <spec.yaml>.")
        return 2
    if not args.spec:
        parser.error("se requiere --from <spec.yaml> (o --interactive)")

    repo_root = find_repo_root()
    spec = load_spec(args.spec)
    if args.no_frontend:
        spec.frontend.generate = False
    if args.no_docs:
        spec.docs.update_claude_md = False

    errors, warnings = validate(spec, repo_root=repo_root)
    for w in warnings:
        print(f"  aviso: {w}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        return 1

    head = current_head(repo_root)
    ctx = build_context(spec, head_rev=head, new_rev=new_revision_id())
    env = make_env()

    try:
        iset = build_insertions(spec, repo_root, ctx, env)
        summary = iset.apply(dry_run=args.dry_run)
    except ValueError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print()
    for line in summary:
        print("  " + line)

    if args.dry_run:
        print("\nSimulacro. Ejecutá sin --dry-run para aplicar.")
    else:
        print(_post_run_block(spec))
    return 0
