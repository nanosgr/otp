# Guía completa del scaffold de recursos CRUD

> Documento de referencia profundo sobre `scripts/scaffold_resource.py` y el paquete
> `scripts/scaffold/`. Complementa a `scripts/scaffold/README.md` (guía rápida de uso)
> con el detalle interno necesario para: (a) entender exactamente qué hace el generador
> y sus límites reales, y (b) que una sesión futura de Claude Code pueda usarlo o
> extenderlo con confianza sin tener que releer todo el código fuente desde cero.
>
> Este documento describe el estado del generador tal como fue auditado el 2026-09-12
> (commit `db0aa00`). Si el código cambia, este documento puede quedar desactualizado —
> ante cualquier discrepancia, el código manda.

## 1. Qué es y para qué sirve

El scaffold es un generador de recursos CRUD que, a partir de un spec YAML, agrega un
recurso nuevo (backend FastAPI + SQLModel, y opcionalmente frontend React) totalmente
integrado al motor RBAC del template: modelo, servicio, endpoints con `require_scope`,
migración Alembic, permisos seedeados para Admin/Manager, página React con tabla +
formulario + control de permisos en la UI, y (opcionalmente) actualización de
`CLAUDE.md`.

No inventa un patrón nuevo: replica en código generado el patrón que ya existe **escrito
a mano** en el dominio de referencia `orders` (`backend/app/api/orders.py`,
`backend/app/models/models.py`, `frontend/src/pages/Orders.tsx`, etc.), que a su vez está
delimitado con marcadores `TEMPLATE:ORDERS:START/END` para poder removerse con
`scripts/remove_orders_domain.py`. `orders` es la "plantilla viva": cualquier ampliación
del generador (nuevo tipo de campo, nuevo patrón de scoping) debería primero explorarse
a mano ahí antes de tocar las plantillas Jinja.

El mecanismo central es genérico: **inserción anclada por texto** (buscar una línea única
en un archivo existente y agregar un bloque antes/después de ella, envuelto en
marcadores `TEMPLATE:<PLURAL>:START/END`) + **archivos nuevos completos** renderizados
con Jinja2. Esto permite tanto generar (`scaffold_resource.py`) como revertir
(`remove_domain.py`) de forma simétrica y, en el caso de reversión, dejar el archivo
**exactamente** igual al original (round-trip byte-limpio).

## 2. Mapa del paquete

```
scripts/scaffold_resource.py     # entry-point CLI (wrapper fino: sys.path + cli.main())
scripts/remove_domain.py         # "undo" genérico para recursos generados por el scaffold
scripts/remove_orders_domain.py  # "undo" específico y hardcodeado para el dominio orders
scripts/scaffold/
├── README.md                    # guía rápida de uso (4 pasos)
├── GUIDE.md                     # este documento
├── spec.py                      # contrato del YAML: dataclasses + load_spec() + validate()
├── cli.py                       # orquestador: argparse, build_insertions(), main()
├── render.py                    # entorno Jinja2 (delimitadores << >>) + build_context()
├── inserts.py                   # motor de anclaje: InsertionSet, render(), apply(), dry-run
├── blocks.py                    # fragmentos backend de 1-2 líneas (f-strings, no Jinja)
├── frontend.py                  # fragmentos frontend (columnas de tabla, campos de form, JSX)
├── typemap.py                   # mapeo tipo de campo -> Python/TS/SQLAlchemy/form
├── domain_files.py              # fuente única de qué archivos toca cada recurso (share cli.py/remove_domain.py)
├── alembic_head.py              # detecta el head de Alembic por regex, sin importar Alembic
├── strip.py                     # elimina bloques entre marcadores (usado por remove_domain.py)
├── specs/
│   └── examples/
│       ├── products.yaml        # ejemplo con scoping "own"
│       └── tickets.yaml         # ejemplo con scoping "attribute"
│   # scripts/scaffold/specs/<plural>.yaml (sin "examples/") = copia canónica
│   # de cada recurso YA generado; la crea el propio cli.py y la usa remove_domain.py.
├── templates/
│   ├── backend/
│   │   ├── api_router.py.jinja      # archivo nuevo completo
│   │   ├── migration.py.jinja       # archivo nuevo completo
│   │   ├── model_block.py.jinja     # bloque insertado en models.py
│   │   ├── service_block.py.jinja   # bloque insertado en crud.py
│   │   └── test_resource.py.jinja   # archivo nuevo completo
│   └── frontend/
│       ├── page.tsx.jinja           # archivo nuevo completo
│       ├── types_block.ts.jinja     # bloque insertado en types/index.ts
│       └── constants_block.ts.jinja # bloque insertado (append_eof) en constants.ts
└── tests/
    ├── conftest.py               # agrega la raíz del repo a sys.path
    └── test_scaffold.py          # tests unitarios del generador (ver sección 8)
```

Por qué `blocks.py`/`frontend.py` NO usan Jinja para los fragmentos chicos: los
genéricos de TypeScript (`Array<T>`) y las llaves de JSX (`{condicion && <div/>}`)
chocan con la sintaxis `{{ }}` de Jinja. Para esos fragmentos puntuales (imports, líneas
de router, ítems de sidebar, objeto de servicio TS) se usan f-strings de Python. Jinja
sólo se usa para los archivos grandes y los bloques de modelo/servicio backend, donde se
configuraron delimitadores custom (`<< variable >>` en vez de `{{ variable }}`,
`render.py`) justamente para poder convivir con código que sí usa `{ }` nativamente.

## 3. El contrato del spec YAML

Definido como `dataclasses` estándar en `scripts/scaffold/spec.py` (no usa Pydantic ni
JSON Schema — validación 100% manual en la función `validate()`).

```yaml
resource:
  singular: product          # obligatorio, snake_case (regex ^[a-z][a-z0-9_]*$)
  plural: products           # obligatorio, snake_case, != singular
  singular_pascal: Product   # opcional, se deriva si falta
  plural_pascal: Products    # opcional, se deriva si falta
  label_singular: Producto   # opcional, se deriva (humanize)
  label_plural: Productos    # opcional, se deriva (humanize)
  icon: Package               # opcional, default "Box"; debería existir en lucide-react
                               # (solo warning si no está en la lista conocida, no bloquea)

fields:                       # al menos 1, nombres únicos y snake_case
  - name: name
    type: string               # string | text | int | float | money | bool | enum
    optional: false             # default false
    default: null                # coherente con el tipo; para enum debe estar en enum_values
    filterable: false            # solo relevante para tabla/UI de frontend
    enum_values:                 # obligatorio si type == enum
      - {value: general, label: General}
      - {value: perishable, label: Perecedero}

scoping:
  mode: none                  # none | own | attribute
  dimension: null               # obligatorio y snake_case si mode == attribute
                                 # (se agrega automáticamente como campo sintético no-opcional)

grants:
  rely_on_auto_inherit: true  # Admin/Manager heredan el recurso vía los loops de init_db.py
  explicit: []                  # no usado activamente por el generador (reservado)
  scoped_demo_roles: false      # NO IMPLEMENTADO — ver sección 6

frontend:
  generate: true               # si false, no genera nada de frontend
  variant: auto                 # auto | plain | scoped

docs:
  update_claude_md: true       # si true, inserta líneas en CLAUDE.md
```

Nombres reservados que no pueden usarse como `resource.singular`/`plural`
(`RESERVED_RESOURCES`): `users, roles, permissions, audit, auth, password, dashboard,
reports, settings`. Nombres de campo reservados (no pueden repetirse como `field.name`):
`id, owner_id, created_at, updated_at` (son estructurales, ya los agrega el generador).

**Validación** (`spec.py:validate()`) devuelve `(errores, warnings)`:
- *Errores* (abortan antes de tocar el disco): identificadores inválidos, colisión con
  recursos reservados, cero campos, campo duplicado o con nombre reservado, tipo
  desconocido, enum sin `enum_values` o con `default` fuera de los valores, `scoping.mode`
  inválido, `attribute` sin `dimension`, `frontend.variant` inválida, y — el chequeo más
  importante para evitar corrupción — **detección de que el recurso ya fue scaffoldeado**
  (busca recursivamente el marcador `TEMPLATE:<PLURAL>:` en `backend/app`, `frontend/src`
  y `scripts/scaffold/specs`; si lo encuentra, exige correr `remove_domain.py` primero).
- *Warnings* (no bloquean): `scoped_demo_roles: true` (se ignora, ver sección 6), icono
  fuera de la lista conocida de lucide-react.

## 4. Qué genera exactamente, archivo por archivo

### 4.1 Archivos nuevos (deben NO existir; si existen, error antes de escribir nada)

| Archivo | Plantilla |
|---|---|
| `backend/app/api/<plural>.py` | `templates/backend/api_router.py.jinja` |
| `backend/alembic/versions/<rev>_add_<plural>.py` | `templates/backend/migration.py.jinja` |
| `backend/tests/test_<plural>.py` | `templates/backend/test_resource.py.jinja` |
| `frontend/src/pages/<PluralPascal>.tsx` (si `frontend.generate`) | `templates/frontend/page.tsx.jinja` |
| `scripts/scaffold/specs/<plural>.yaml` | copia literal del YAML de entrada (referencia canónica para `remove_domain.py`) |

### 4.2 Archivos existentes editados por inserción anclada

Cada bloque queda envuelto en marcadores `TEMPLATE:<PLURAL_UPPER>:START/END` (estilo de
comentario según el lenguaje: `#` en Python, `//` en TS, `{/* */}` en JSX, `<!-- -->` en
Markdown).

**Backend:**
- `backend/app/models/models.py` — bloque con `<S>Base`, `<S>` (SQLModel `table=True`),
  `<S>Create`, `<S>Read`, `<S>Update`, insertado `before` `"# Resolver referencias
  circulares"`.
- `backend/app/services/crud.py` — 3 inserciones: import de tipos (`after` el import de
  `User/Role/Permission`), clase `<S>Service` (`before` `"user_service =
  UserService()"`), instancia global (`after` `"user_scope_service =
  UserScopeService()"`).
- `backend/app/api/__init__.py` — import del router + `include_router(...)`.
- `backend/app/db/init_db.py` — bloque de permisos `<plural>:create/read/update/delete`
  (`before` el comentario de wildcards); Admin/Manager los heredan automáticamente por
  los loops ya existentes en ese archivo (no requiere código de grant explícito).
- `backend/alembic/env.py` — import del modelo nuevo (para que `--autogenerate` lo vea).
- `backend/app/core/deps.py` — **solo si `scoping.mode == none`**: agrega helpers
  `require_<singular>_<action>()` análogos a `require_user_read()`.

**Frontend** (solo si `frontend.generate`):
- `frontend/src/App.tsx` — import de la página + `<Route>` nueva.
- `frontend/src/lib/api/services.ts` — import de tipos DTO + objeto `<singular>Service`
  (getAll/getById/create/update/delete).
- `frontend/src/types/index.ts` — interfaces `<S>`, `Create<S>DTO`, `Update<S>DTO`,
  `Get<Plural>Params`.
- `frontend/src/lib/constants.ts` — **solo si hay campos `enum`**: constantes de opciones
  (modo `append_eof`, al final del archivo).
- `frontend/src/components/layout/Sidebar.tsx` — icono lucide + ítem de navegación.

**Docs** (solo si `docs.update_claude_md`): una línea de endpoint y una de esquema
insertadas en `CLAUDE.md`.

### 4.3 Motor de anclaje (`inserts.py`)

- Resolución de anchor por **substring literal** (no regex, no AST): recorre línea por
  línea buscando dónde aparece el string ancla; si aparece 0 o 2+ veces, `ValueError`
  (`"el anchor {anchor!r} apareció {n} veces (se esperaba 1)"`) — nunca inserta "a
  ciegas" en una posición ambigua.
- Modos: `before`, `after`, `append_eof` (ignora el anchor, va al final del archivo).
- Indentación tomada automáticamente de la línea ancla salvo override explícito.
- **Atomicidad**: `render()` calcula el contenido nuevo de *todos* los archivos en
  memoria antes de escribir ninguno. Si un solo anchor falla en cualquier archivo, se
  aborta todo el proceso sin tocar el disco ("todo o nada").
- **`--dry-run`**: corre exactamente el mismo pipeline de resolución de anchors (por lo
  tanto también detecta errores), pero en vez de escribir imprime preview completo (hasta
  120 líneas) de los archivos nuevos y diff unificado (`difflib.unified_diff`) de los
  archivos editados. Cero escritura a disco.
- Diseño clave para la reversión limpia: la línea en blanco de separación se inserta
  **dentro** de los marcadores `START`/`END` (no fuera), de modo que al quitar el bloque
  completo no queda ningún resto en el archivo (ver sección 5).

## 5. Cómo se deshace un recurso

### 5.1 `scripts/remove_domain.py <plural>` (genérico, para recursos generados por el scaffold)

1. Busca el spec canónico en `scripts/scaffold/specs/<plural>.yaml` (la copia que el
   propio generador guardó); si no existe, aborta (asume que el recurso nunca fue
   scaffoldeado con esta herramienta).
2. Usa `domain_files.files_to_delete(spec, repo_root)` y
   `domain_files.files_with_markers(spec)` — la misma "fuente única de verdad" que usa
   `cli.py` para generar — para saber qué borrar entero y qué recortar.
3. Borra los archivos 100% del dominio (incluye también las migraciones Alembic
   encontradas por glob y la copia del spec).
4. Para los archivos compartidos, aplica `strip.py::strip_marker_blocks(text, tag)`:
   recorre línea por línea contando profundidad de anidamiento de
   `TAG:START`/`TAG:END`, descarta las líneas dentro de los marcadores (incluidos los
   marcadores mismos), colapsa 4+ saltos de línea consecutivos a 3, y lanza `ValueError`
   si los marcadores quedan desbalanceados.
5. Es **idempotente**: correrlo de nuevo sobre un recurso ya removido no falla, informa
   "nada que hacer".
6. Al final imprime pasos manuales pendientes: `alembic downgrade -1` (o migración
   manual), correr pytest backend, `npm run build` frontend. **No** hace downgrade de
   base de datos ni rebuild automáticamente.

La garantía de que el archivo quede **byte a byte** igual al original (no sólo
"parecido") depende de que la blank line de separación se agregó *dentro* del bloque
marcado al insertar — así, quitar `START...bloque...blank line...END` completo no deja
ningún resto. Esto está probado explícitamente en
`test_scaffold.py::test_insertion_roundtrip_is_identity` (inserta, luego quita, compara
`resultado == original` byte a byte). No hay checksum contra un snapshot previo: la
garantía es por construcción (marcadores balanceados 1:1), no por comparación.

### 5.2 `scripts/remove_orders_domain.py` (específico y hardcodeado para `orders`)

Mismo algoritmo (`strip_marker_blocks` con `TEMPLATE:ORDERS`), pero con las listas de
archivos (`FILES_TO_DELETE`, `FILES_WITH_MARKERS`) escritas a mano en el propio script,
porque `orders` es la plantilla original escrita a mano (nunca pasó por
`scaffold_resource.py`, así que no tiene un spec YAML commiteado en
`scripts/scaffold/specs/`). Si en algún momento se quisiera regenerar `orders` con el
generador genérico, habría que escribirle un `orders.yaml` — hoy no existe.

## 6. Limitaciones conocidas (confirmadas en código, no solo documentadas)

| Limitación | Evidencia en código |
|---|---|
| `grants.scoped_demo_roles` no implementado | `spec.py` declara el campo pero sólo emite un *warning*; no se lee en `cli.py`, `blocks.py`, `render.py` ni en ninguna plantilla. Si se necesitan roles demo con scope (tipo `Vendedor`/`Jefe de Depósito` de `orders`), hay que agregarlos a mano en `init_db.py` siguiendo ese mismo patrón (`_ensure_link(db, role.id, perm.id, scope="own")` / `scope="attribute", scope_dimension=...`). |
| Tipos `date`/`datetime` no soportados | `FIELD_TYPES` en `spec.py` no los incluye; un spec con `type: date` es rechazado en `validate()`. Pendiente: widgets de fecha en el form + import condicional en `models.py`. |
| `--interactive` no implementado | El flag existe en `cli.py` pero sólo imprime el aviso y retorna código 2. Siempre hay que usar `--from <spec.yaml>`. |
| `permissions.py::get_available_resources()` no se actualiza automáticamente | Lista hardcodeada; el generador lo señala como paso manual opcional en el resumen post-run. |
| La migración Alembic generada no se testea automáticamente | Los tests del generador usan SQLite in-memory vía `SQLModel.metadata.create_all`, no ejecutan la migración real. Las migraciones están pensadas para PostgreSQL (estilo `sa.*` plano). |
| No hay variantes de frontend más allá de `auto`/`plain`/`scoped` | Cualquier UI custom (wizards, vistas maestro-detalle, gráficos) requiere edición manual post-generación. |

## 7. Guía operativa paso a paso

### 7.1 Agregar un recurso nuevo

1. Copiar el ejemplo más parecido de `scripts/scaffold/specs/examples/`:
   - `products.yaml` si el recurso necesita scoping por dueño (`scoping.mode: own`,
     agrega columna `owner_id`) — es también el ejemplo más completo de tipos de campo.
   - `tickets.yaml` si necesita scoping por atributo de negocio (`scoping.mode:
     attribute`, ej. `team`, `warehouse`, `zone`) — análogo al caso "Jefe de Depósito"
     de `orders`.
   - Si el recurso no necesita scoping de datos (permisos planos, como en `users` /
     `roles`), usar `scoping.mode: none` (no hay ejemplo dedicado, pero está cubierto y
     testeado — ver `test_scaffold.py`).
2. Editar el YAML: `resource.singular/plural`, `fields`, y desactivar
   `frontend.generate`/`docs.update_claude_md` si no aplican.
3. Instalar dependencias de desarrollo si no están: `cd backend && ./venv/bin/pip
   install -r requirements-dev.txt` (PyYAML + Jinja2 + pytest).
4. Ejecutar primero `python scripts/scaffold_resource.py --from <spec>.yaml --dry-run`
   y revisar los diffs/previews impresos.
5. Ejecutar sin `--dry-run` para aplicar.
6. Seguir el bloque "SIGUIENTES PASOS" que imprime el propio comando: aplicar la
   migración (`alembic upgrade head`), re-seedear (`init_db`), correr pytest backend,
   `npm run build` frontend, y — si corresponde — agregar el recurso a
   `permissions.py::get_available_resources()` a mano.
7. Si se necesitan roles demo con scope (equivalente a `Vendedor`/`Jefe de Depósito`),
   agregarlos manualmente en `backend/app/db/init_db.py` replicando el patrón usado para
   `orders` (sección `TEMPLATE:ORDERS` de ese archivo).

### 7.2 Revertir un recurso generado por el scaffold

```bash
python scripts/remove_domain.py <plural> --dry-run   # revisar qué se borraría/editaría
python scripts/remove_domain.py <plural>
```
Luego seguir los pasos manuales que imprime (downgrade de Alembic o migración manual,
pytest, `npm run build`).

### 7.3 Checklist: ¿el scaffold alcanza, o hay que escribir código a mano?

Escribir a mano (o extender el generador primero, ver 7.4) si el recurso necesita:
- Campos de fecha/hora (`date`/`datetime`).
- Roles demo con scope pre-seedeados automáticamente.
- Actualización automática de `get_available_resources()`.
- Una UI de frontend que no sea tabla + modal de formulario simple (wizards, vistas
  anidadas, gráficos, drag-and-drop, etc.).
- Relaciones entre recursos (foreign keys hacia otro modelo custom, más allá de
  `owner_id` hacia `users`) — el generador no contempla relaciones entre recursos
  generados.

### 7.4 Cómo extender el generador mismo

Si hace falta soportar una capacidad nueva (ejemplo: tipo `date`):
1. `scripts/scaffold/spec.py` — agregar el tipo a `FIELD_TYPES` y las reglas de
   validación que correspondan (`validate()`).
2. `scripts/scaffold/typemap.py` — agregar el mapeo del tipo nuevo a línea de modelo
   SQLModel, columna Alembic, tipo TypeScript, valor por defecto de formulario, etc.
3. `scripts/scaffold/templates/**/*.jinja` — ajustar las plantillas que renderizan
   campos (modelo, servicio, página TSX) si el tipo nuevo necesita tratamiento especial
   (ej. un widget de date picker en el form, un import condicional en `models.py`).
4. `scripts/scaffold/domain_files.py` — sólo si el tipo nuevo requiere tocar un archivo
   adicional no contemplado hoy.
5. `scripts/scaffold/tests/test_scaffold.py` — agregar cobertura análoga a los tests
   parametrizados existentes (`test_generated_backend_is_valid_python`,
   `test_build_insertions_produce_valid_python`) para el caso nuevo.
6. Correr `python -m pytest scripts/scaffold/tests -q` para validar que no se rompió
   nada existente.
7. Si el cambio toca el mecanismo de scoping o el patrón de permisos, primero
   implementarlo/probarlo a mano en `orders` (el dominio de referencia) antes de
   automatizarlo en el generador — es la fuente de verdad del patrón.

## 8. Cobertura de tests del generador (`scripts/scaffold/tests/test_scaffold.py`)

- `test_current_head_is_single` — un único head de Alembic.
- Validación de spec: spec de ejemplo válido, rechazo de recursos reservados, rechazo de
  enum sin `enum_values`, agregado automático del campo de dimensión en `scoping:
  attribute`.
- `test_insertion_requires_unique_anchor` — anchor duplicado debe fallar.
- `test_insertion_roundtrip_is_identity` — prueba explícita de round-trip byte a byte
  (insertar + quitar = original).
- `test_generated_backend_is_valid_python` (parametrizado por `none`/`own`/`attribute`)
  — cada plantilla backend renderiza a Python sintácticamente válido (`ast.parse`).
- `test_build_insertions_produce_valid_python` (parametrizado igual) — simulación tipo
  dry-run contra el árbol real del repo; todos los `.py` resultantes son válidos.
- `test_domain_files_consistent` — `files_with_markers()` y `files_to_delete()` son
  listas disjuntas y contienen las entradas esperadas.

No hay un test end-to-end que ejecute el CLI completo y luego `remove_domain.py` sobre
un recurso recién generado; la garantía de reversión se prueba a nivel de las piezas
(`InsertionSet`/`strip_marker_blocks`) y de consistencia de listas de archivos, no del
flujo completo en un checkout real.
