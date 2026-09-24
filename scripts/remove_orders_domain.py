#!/usr/bin/env python3
"""Elimina el dominio de ejemplo *orders / pedidos* de esta plantilla RBAC.

Esta plantilla incluye un modelo de dominio de ejemplo (`orders`) que sólo sirve
para demostrar el motor de *data scoping* (`scope="own" / "attribute"`, tabla
`user_scopes`, `require_scope`, editores de scope en el frontend). El motor de
scoping es genérico y se conserva; lo único que se borra es ese modelo de ejemplo
y todo lo que cuelga de él.

Cómo funciona
-------------
- Los bloques de código acoplados a `orders` están rodeados por marcadores
  centinela en el código fuente:

      # TEMPLATE:ORDERS:START   ...   # TEMPLATE:ORDERS:END      (Python)
      // TEMPLATE:ORDERS:START  ...   // TEMPLATE:ORDERS:END      (TS/TSX)
      {/* TEMPLATE:ORDERS:START */} ... {/* TEMPLATE:ORDERS:END */}  (JSX)
      <!-- TEMPLATE:ORDERS:START --> ... <!-- TEMPLATE:ORDERS:END -->  (Markdown)

  El script borra esas líneas y todo lo que hay entre ellas (marcadores incluidos).
- Los archivos que son 100% del dominio de ejemplo se eliminan por completo.

Qué se conserva
---------------
- El motor de scoping genérico: columnas `role_permissions.scope` /
  `scope_dimension`, tabla `user_scopes`, `rbac.resolve_scope`, `Scope`,
  `require_scope` / `ScopedAccess`, wildcards, reglas DENY, assertions.
- Los editores de scope de las páginas Roles y Users del frontend.
- La jerarquía de roles y su demo (Admin -> Manager -> User), la regla DENY del
  Viewer y la assertion `owner` del rol User (no dependen de `orders`).

Uso
---
    python scripts/remove_orders_domain.py --dry-run   # muestra qué haría
    python scripts/remove_orders_domain.py             # aplica los cambios

Después de aplicarlo hay que recrear la base de datos de desarrollo o correr las
migraciones desde cero (ver el resumen que imprime el script).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

START = "TEMPLATE:ORDERS:START"
END = "TEMPLATE:ORDERS:END"

# Archivos que se eliminan por completo (son sólo del dominio de ejemplo).
FILES_TO_DELETE = [
    "backend/app/api/orders.py",
    "backend/tests/test_scoping.py",
    "frontend/src/pages/Orders.tsx",
]

# Archivos compartidos: se les quitan sólo los bloques entre marcadores centinela.
FILES_WITH_MARKERS = [
    "backend/app/api/__init__.py",
    "backend/app/services/crud.py",
    "backend/app/models/models.py",
    "backend/app/db/init_db.py",
    "backend/alembic/env.py",
    "backend/alembic/versions/a1b2c3d4e5f6_add_data_scoping.py",
    "frontend/src/App.tsx",
    "frontend/src/lib/api/services.ts",
    "frontend/src/types/index.ts",
    "frontend/src/lib/constants.ts",
    "frontend/src/components/layout/Sidebar.tsx",
    "CLAUDE.md",
]


def find_repo_root() -> Path:
    """Sube desde este archivo hasta encontrar la raíz del repo (backend/ + frontend/)."""
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "backend").is_dir() and (candidate / "frontend").is_dir():
            return candidate
    print("ERROR: no encuentro la raíz del repo (esperaba carpetas backend/ y frontend/).")
    sys.exit(1)


def strip_marker_blocks(text: str) -> tuple[str, int]:
    """Devuelve (texto_sin_bloques, cantidad_de_bloques_eliminados)."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    removed = 0
    depth = 0
    for line in lines:
        if START in line:
            depth += 1
            continue
        if END in line:
            if depth > 0:
                depth -= 1
                if depth == 0:
                    removed += 1
            continue
        if depth == 0:
            out.append(line)
    if depth != 0:
        raise ValueError("marcadores TEMPLATE:ORDERS desbalanceados")
    result = "".join(out)
    # Colapsa 3+ líneas en blanco consecutivas (que deja la eliminación) a 2.
    while "\n\n\n\n" in result:
        result = result.replace("\n\n\n\n", "\n\n\n")
    return result, removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="muestra los cambios sin escribir nada")
    args = parser.parse_args()

    root = find_repo_root()
    dry = args.dry_run
    tag = "[dry-run] " if dry else ""

    changed = 0
    deleted = 0
    missing: list[str] = []
    no_markers: list[str] = []

    print(f"Raíz del repo: {root}\n")

    # 1) Eliminar archivos completos.
    for rel in FILES_TO_DELETE:
        path = root / rel
        if not path.exists():
            missing.append(rel)
            continue
        print(f"{tag}borrar archivo   {rel}")
        if not dry:
            path.unlink()
        deleted += 1

    # 2) Quitar bloques marcados de archivos compartidos.
    for rel in FILES_WITH_MARKERS:
        path = root / rel
        if not path.exists():
            missing.append(rel)
            continue
        original = path.read_text(encoding="utf-8")
        if START not in original:
            no_markers.append(rel)
            continue
        try:
            new_text, blocks = strip_marker_blocks(original)
        except ValueError as exc:
            print(f"ERROR en {rel}: {exc}")
            return 1
        print(f"{tag}editar           {rel}  ({blocks} bloque(s) eliminado(s))")
        if not dry and new_text != original:
            path.write_text(new_text, encoding="utf-8")
        changed += 1

    # 3) Resumen.
    print()
    print(f"Archivos eliminados: {deleted}")
    print(f"Archivos editados:   {changed}")
    if no_markers:
        print("\nSin marcadores TEMPLATE:ORDERS (ya limpios, se omiten):")
        for rel in no_markers:
            print(f"  - {rel}")
    if missing:
        print("\nNo encontrados (¿ya eliminados?):")
        for rel in missing:
            print(f"  - {rel}")

    if deleted == 0 and changed == 0:
        print("\nNada que hacer: el dominio orders ya fue eliminado.")
        return 0

    if dry:
        print("\nEsto fue un simulacro. Ejecuta sin --dry-run para aplicar los cambios.")
        return 0

    print(
        "\n" + "=" * 70 + "\n"
        "SIGUIENTE PASO — recrear el esquema de base de datos\n"
        + "=" * 70 + "\n"
        "El dominio orders ya no existe en los modelos ni en el seed. Elige una vía:\n\n"
        "  A) Recrear desde SQLAlchemy (desarrollo, borra datos):\n"
        "       cd backend && source venv/bin/activate\n"
        "       python -c \"from app.db.init_db import create_tables, init_db; create_tables(); init_db()\"\n\n"
        "  B) Migraciones Alembic desde cero (base vacía):\n"
        "       cd backend && alembic upgrade head\n\n"
        "  C) Si ya tenías la tabla 'orders' creada en una base que quieres conservar:\n"
        "       cd backend && alembic revision -m \"drop orders table\"   # y en upgrade(): op.drop_table('orders')\n\n"
        "Frontend: revisa que compile\n"
        "  cd frontend && npm run build\n\n"
        "Tests: test_scoping.py se eliminó. La cobertura del motor RBAC/scoping\n"
        "queda en backend/tests/test_rbac_engine.py y test_roles_api.py.\n\n"
        "Revisa el diff (git diff) y commitea cuando estés conforme."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
