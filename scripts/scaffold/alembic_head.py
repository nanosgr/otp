"""Detecta la revisión Alembic *head* parseando `backend/alembic/versions/*.py`.

No importa Alembic ni toca la base de datos: sólo lee los literales `revision` /
`down_revision` de cada archivo. El head es la revisión que ningún archivo
referencia como `down_revision`.
"""
from __future__ import annotations

import re
from pathlib import Path

_REV_RE = re.compile(r"^revision\s*[:=].*?['\"]([^'\"]+)['\"]", re.M)
_DOWN_RE = re.compile(r"^down_revision\s*[:=].*?['\"]([^'\"]+)['\"]", re.M)


def versions_dir(repo_root: Path) -> Path:
    return repo_root / "backend" / "alembic" / "versions"


def current_head(repo_root: Path) -> str:
    """Devuelve la revisión head. Aborta si hay 0 o >1 (historia ramificada)."""
    vdir = versions_dir(repo_root)
    revs: dict[str, str] = {}
    downs: set[str] = set()
    for p in sorted(vdir.glob("*.py")):
        text = p.read_text(encoding="utf-8")
        rm = _REV_RE.search(text)
        dm = _DOWN_RE.search(text)
        if rm:
            revs[rm.group(1)] = p.name
        if dm:
            downs.add(dm.group(1))

    if not revs:
        raise SystemExit(f"No encontré migraciones en {vdir}")

    heads = [r for r in revs if r not in downs]
    if len(heads) != 1:
        raise SystemExit(
            f"Se esperaba exactamente 1 head Alembic, hay {len(heads)}: {heads}. "
            f"Resolvé la historia ramificada antes de scaffoldear."
        )
    return heads[0]
