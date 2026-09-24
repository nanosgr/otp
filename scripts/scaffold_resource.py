#!/usr/bin/env python3
"""Genera un recurso CRUD nuevo (backend FastAPI/SQLModel + frontend React) a
partir de un spec YAML, siguiendo el patrón del dominio de referencia `orders`.

    python scripts/scaffold_resource.py --from scripts/scaffold/specs/products.yaml --dry-run
    python scripts/scaffold_resource.py --from scripts/scaffold/specs/products.yaml

Ver `scripts/scaffold/cli.py` y el spec de ejemplo en `scripts/scaffold/specs/`.
Para deshacer un recurso generado: `python scripts/remove_domain.py <plural>`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.scaffold.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
