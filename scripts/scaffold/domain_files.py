"""Fuente única de verdad: qué archivos toca el dominio de un recurso.

Importado por el generador y por `scripts/remove_domain.py` para que ambos
coincidan exactamente.
"""
from __future__ import annotations

from pathlib import Path

from .spec import Spec


def spec_rel_path(spec: Spec) -> str:
    return f"scripts/scaffold/specs/{spec.resource.plural}.yaml"


def find_migration_files(repo_root: Path, plural: str) -> list[str]:
    vdir = repo_root / "backend" / "alembic" / "versions"
    return sorted(
        str(p.relative_to(repo_root)) for p in vdir.glob(f"*_add_{plural}.py")
    )


def files_to_delete(spec: Spec, repo_root: Path | None = None) -> list[str]:
    """Archivos 100% del dominio (se borran enteros)."""
    p = spec.resource.plural
    files = [
        f"backend/app/api/{p}.py",
        f"backend/tests/test_{p}.py",
        spec_rel_path(spec),
    ]
    if spec.frontend.generate:
        files.append(f"frontend/src/pages/{spec.resource.plural_pascal}.tsx")
    if repo_root is not None:
        files.extend(find_migration_files(repo_root, p))
    return files


def files_with_markers(spec: Spec) -> list[str]:
    """Archivos compartidos: se les quitan los bloques entre marcadores."""
    files = [
        "backend/app/api/__init__.py",
        "backend/app/services/crud.py",
        "backend/app/models/models.py",
        "backend/app/db/init_db.py",
        "backend/alembic/env.py",
    ]
    if not spec.is_scoped:
        files.append("backend/app/core/deps.py")
    if spec.frontend.generate:
        files += [
            "frontend/src/App.tsx",
            "frontend/src/lib/api/services.ts",
            "frontend/src/types/index.ts",
            "frontend/src/components/layout/Sidebar.tsx",
        ]
        if spec.enum_fields:
            files.append("frontend/src/lib/constants.ts")
    if spec.docs.update_claude_md:
        files.append("CLAUDE.md")
    return files
