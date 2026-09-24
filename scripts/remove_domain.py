#!/usr/bin/env python3
"""Elimina un recurso generado por `scripts/scaffold_resource.py`.

    python scripts/remove_domain.py <plural> [--dry-run]

Lee el spec commiteado en `scripts/scaffold/specs/<plural>.yaml` para saber qué
archivos tocó el recurso, borra los archivos propios y quita los bloques entre
marcadores `TEMPLATE:<PLURAL_UPPER>:START/END` de los compartidos. Idempotente.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.scaffold import domain_files  # noqa: E402
from scripts.scaffold.cli import find_repo_root  # noqa: E402
from scripts.scaffold.spec import load_spec  # noqa: E402
from scripts.scaffold.strip import strip_marker_blocks  # noqa: E402


def run(plural: str, *, dry_run: bool) -> int:
    repo_root = find_repo_root()
    tag = f"TEMPLATE:{plural.upper()}"
    spec_path = repo_root / f"scripts/scaffold/specs/{plural}.yaml"
    if not spec_path.exists():
        print(f"ERROR: no existe {spec_path.relative_to(repo_root)}; "
              f"¿el recurso {plural!r} fue generado con scaffold_resource.py?",
              file=sys.stderr)
        return 1

    spec = load_spec(spec_path)
    to_delete = domain_files.files_to_delete(spec, repo_root)
    with_markers = domain_files.files_with_markers(spec)
    tag_prefix = "[dry-run] " if dry_run else ""

    deleted = changed = 0

    for rel in to_delete:
        path = repo_root / rel
        if not path.exists():
            continue
        print(f"{tag_prefix}borrar   {rel}")
        if not dry_run:
            path.unlink()
        deleted += 1

    for rel in with_markers:
        path = repo_root / rel
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        if f"{tag}:" not in original:
            continue
        try:
            new_text, blocks = strip_marker_blocks(original, tag)
        except ValueError as exc:
            print(f"ERROR en {rel}: {exc}", file=sys.stderr)
            return 1
        print(f"{tag_prefix}editar   {rel}  ({blocks} bloque(s))")
        if not dry_run and new_text != original:
            path.write_text(new_text, encoding="utf-8")
        changed += 1

    print(f"\nArchivos borrados: {deleted} | editados: {changed}")
    if deleted == 0 and changed == 0:
        print(f"Nada que hacer: el recurso {plural!r} ya fue removido.")
        return 0
    if dry_run:
        print("\nSimulacro. Ejecutá sin --dry-run para aplicar.")
    else:
        print(
            "\nSIGUIENTES PASOS\n"
            "  1. git diff\n"
            "  2. Quitá la migración de la base:  cd backend && ./venv/bin/alembic downgrade -1\n"
            "     (o recreá el esquema desde cero)\n"
            "  3. cd backend && ./venv/bin/pytest\n"
            "  4. cd frontend && npm run build"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="remove_domain")
    parser.add_argument("plural", help="nombre plural del recurso (ej. products)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run(args.plural, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
