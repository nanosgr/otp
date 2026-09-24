# Generador de scaffold de recursos

Agrega un modelo de datos CRUD nuevo y cablea **todo** lo necesario en backend
(FastAPI + SQLModel) y frontend (React + Vite), siguiendo el patrón del dominio de
referencia `orders` y su convención de marcadores centinela.

## Uso

```bash
# 1. copiá un ejemplo y editalo
cp scripts/scaffold/specs/examples/products.yaml /tmp/mi-recurso.yaml
$EDITOR /tmp/mi-recurso.yaml

# 2. simulá
python scripts/scaffold_resource.py --from /tmp/mi-recurso.yaml --dry-run

# 3. aplicá
python scripts/scaffold_resource.py --from /tmp/mi-recurso.yaml

# 4. seguí los "SIGUIENTES PASOS" que imprime (migración, re-seed, pytest, npm run build)

# para deshacer:
python scripts/remove_domain.py <plural>
```

Requiere las deps dev: `cd backend && ./venv/bin/pip install -r requirements-dev.txt`.

## Qué genera

| Capa | Archivos nuevos | Archivos editados (bloques entre marcadores `TEMPLATE:<PLURAL>:START/END`) |
|---|---|---|
| Backend | `app/api/<plural>.py`, `alembic/versions/<rev>_add_<plural>.py`, `tests/test_<plural>.py` | `app/models/models.py`, `app/services/crud.py`, `app/api/__init__.py`, `app/db/init_db.py`, `alembic/env.py`, `app/core/deps.py` (sólo si `scoping.mode == none`) |
| Frontend | `src/pages/<PluralPascal>.tsx` | `src/App.tsx`, `src/lib/api/services.ts`, `src/types/index.ts`, `src/lib/constants.ts` (si hay `enum`), `src/components/layout/Sidebar.tsx` |
| Docs | — | `CLAUDE.md` |
| Spec | `scripts/scaffold/specs/<plural>.yaml` (copia canónica; la usa `remove_domain.py`) | — |

## Spec YAML

Ver `specs/examples/`. Campos:

- `resource.{singular,plural}` (obligatorio, snake_case). `singular_pascal`,
  `plural_pascal`, `label_singular`, `label_plural`, `icon` se derivan si faltan.
- `fields[]`: `{ name, type, optional?, default?, filterable?, enum_values? }`.
  Tipos: `string`, `text`, `int`, `float`, `money`, `bool`, `enum`.
- `scoping.mode`: `none` (permiso plano) | `own` (columna `owner_id`) |
  `attribute` (+`dimension`, que pasa a ser un campo requerido).
- `frontend.generate` (default `true`), `docs.update_claude_md` (default `true`).

### Grants

Los roles `Admin` (todos los permisos concretos) y `Manager` (read/update)
**heredan el recurso automáticamente** por los loops de `init_db.py`. No hace falta
código de grant. Un recurso con scoping igual queda usable por `admin`/`manager`.

## Limitaciones actuales

- `grants.scoped_demo_roles` **no implementado**: no genera roles/usuarios demo
  tipo `Vendedor`/`Jefe de Deposito`. Agregalos a mano en `init_db.py` si querés un
  demo de scope; el motor (`require_scope`, `Scope`, `user_scopes`) ya es genérico.
- Tipos `date` / `datetime`: no soportados todavía (widgets de fecha pendientes).
- `permissions.py::get_available_resources()` tiene una lista hardcodeada que el
  generador no toca (paso manual opcional en el bloque post-run).
- La migración se genera para PostgreSQL (estilo `sa.*` plano). Los tests usan
  SQLite in-memory vía `SQLModel.metadata.create_all`, no la migración.

## Tests del propio generador

```bash
python -m pytest scripts/scaffold/tests -q
```
