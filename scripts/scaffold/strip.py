"""Quita bloques entre marcadores centinela `<TAG>:START` / `<TAG>:END`.

Compartido por `scripts/remove_domain.py` y `scripts/remove_orders_domain.py`.
"""
from __future__ import annotations


def strip_marker_blocks(text: str, tag: str) -> tuple[str, int]:
    """Devuelve `(texto_sin_bloques, cantidad_eliminada)`. Soporta anidamiento."""
    start = f"{tag}:START"
    end = f"{tag}:END"
    out: list[str] = []
    removed = 0
    depth = 0
    for line in text.splitlines(keepends=True):
        if start in line:
            depth += 1
            continue
        if end in line:
            if depth > 0:
                depth -= 1
                if depth == 0:
                    removed += 1
            continue
        if depth == 0:
            out.append(line)
    if depth != 0:
        raise ValueError(f"marcadores {tag} desbalanceados")
    result = "".join(out)
    while "\n\n\n\n" in result:
        result = result.replace("\n\n\n\n", "\n\n\n")
    return result, removed
