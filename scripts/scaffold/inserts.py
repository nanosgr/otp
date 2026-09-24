"""Motor de inserción anclada + creación de archivos, con dry-run atómico.

- `add_file(rel, content)` — archivo nuevo (falla si ya existe).
- `add_insertion(rel, anchor, block, mode, style, tag)` — inserta un bloque
  envuelto en marcadores centinela relativo a la única línea que contiene `anchor`.

Nada se escribe hasta que TODOS los anchors resolvieron a exactamente una línea.
"""
from __future__ import annotations

import difflib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_MARKER = {
    "py": "# {}",
    "ts": "// {}",
    "jsx": "{{/* {} */}}",
    "md": "<!-- {} -->",
}


def _leading_ws(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def marker(style: str, tag: str, which: str) -> str:
    return _MARKER[style].format(f"{tag}:{which}")


@dataclass
class _Insertion:
    anchor: str
    block: str
    mode: str  # before | after | append_eof
    style: str
    tag: str
    indent: str | None = None
    spaced: bool = True


@dataclass
class InsertionSet:
    repo_root: Path
    _edits: dict[Path, list[_Insertion]] = field(default_factory=lambda: defaultdict(list))
    _new: dict[Path, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ builders

    def add_file(self, rel_path: str, content: str) -> None:
        self._new[self.repo_root / rel_path] = content

    def add_insertion(self, rel_path: str, anchor: str, block: str, mode: str,
                      style: str, tag: str, *, indent: str | None = None,
                      spaced: bool = True) -> None:
        assert mode in ("before", "after", "append_eof")
        self._edits[self.repo_root / rel_path].append(
            _Insertion(anchor, block, mode, style, tag, indent, spaced)
        )

    # ------------------------------------------------------------------- render

    def render(self) -> dict[Path, tuple[str | None, str]]:
        """{path: (contenido_viejo_o_None, contenido_nuevo)}. Levanta ValueError
        si algún anchor no resuelve unívocamente o un archivo nuevo ya existe."""
        out: dict[Path, tuple[str | None, str]] = {}

        for path, content in self._new.items():
            if path.exists():
                raise ValueError(f"el archivo ya existe: {path}")
            out[path] = (None, content)

        for path, inss in self._edits.items():
            if not path.exists():
                raise ValueError(f"anchor target no existe: {path}")
            old = path.read_text(encoding="utf-8")
            lines = old.splitlines(keepends=True)

            ops: list[tuple[int, str]] = []
            for ins in inss:
                idx = self._resolve(path, lines, ins)
                wrapped = self._wrap(ins, lines, idx)
                pos = {
                    "before": idx,
                    "after": idx + 1,
                    "append_eof": len(lines),
                }[ins.mode]
                ops.append((pos, wrapped))

            # aplicar de mayor a menor posición para no correr los índices
            for pos, wrapped in sorted(ops, key=lambda t: t[0], reverse=True):
                lines[pos:pos] = wrapped.splitlines(keepends=True)

            out[path] = (old, "".join(lines))

        return out

    # ------------------------------------------------------------------ helpers

    def _resolve(self, path: Path, lines: list[str], ins: _Insertion) -> int:
        if ins.mode == "append_eof":
            return len(lines)
        hits = [i for i, ln in enumerate(lines) if ins.anchor in ln]
        if len(hits) != 1:
            rel = path
            try:
                rel = path.relative_to(self.repo_root)
            except ValueError:
                pass
            raise ValueError(
                f"{rel}: el anchor {ins.anchor!r} apareció {len(hits)} veces "
                f"(se esperaba 1)"
            )
        return hits[0]

    def _wrap(self, ins: _Insertion, lines: list[str], idx: int) -> str:
        if ins.indent is not None:
            indent = ins.indent
        elif ins.mode == "append_eof":
            indent = ""
        else:
            indent = _leading_ws(lines[idx])

        body = [
            (indent + ln).rstrip() if ln.strip() else ""
            for ln in ins.block.strip("\n").split("\n")
        ]
        # La separación en blanco va DENTRO de los marcadores para que el
        # remover deje el archivo idéntico al original (round-trip limpio).
        if ins.spaced:
            if ins.mode == "before":
                body = [*body, ""]
            else:  # after | append_eof
                body = ["", *body]
        block_lines = [
            indent + marker(ins.style, ins.tag, "START"),
            *body,
            indent + marker(ins.style, ins.tag, "END"),
        ]
        return "\n".join(block_lines) + "\n"

    # -------------------------------------------------------------------- apply

    def apply(self, *, dry_run: bool) -> list[str]:
        rendered = self.render()
        summary: list[str] = []
        for path, (old, new) in sorted(rendered.items()):
            try:
                rel = str(path.relative_to(self.repo_root))
            except ValueError:
                rel = str(path)
            if old is None:
                summary.append(f"{'[dry-run] ' if dry_run else ''}crear   {rel}")
                if dry_run:
                    print(f"\n=== NUEVO {rel} ===")
                    print(_preview(new))
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(new, encoding="utf-8")
            else:
                summary.append(f"{'[dry-run] ' if dry_run else ''}editar  {rel}")
                if dry_run:
                    diff = difflib.unified_diff(
                        old.splitlines(keepends=True), new.splitlines(keepends=True),
                        fromfile=f"a/{rel}", tofile=f"b/{rel}",
                    )
                    print("".join(diff), end="")
                else:
                    path.write_text(new, encoding="utf-8")
        return summary


def _preview(text: str, limit: int = 120) -> str:
    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:limit] + [f"… (+{len(lines) - limit} líneas)"])
