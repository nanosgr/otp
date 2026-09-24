# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

online-otp: sistema de liquidación de jubilaciones/retiros y pensiones del personal policial de la provincia de Mendoza (Oficina Técnico Previsional). Stack: React + Vite (frontend), FastAPI + SQLModel + Alembic (backend), PostgreSQL, y un motor de fórmulas en Rust (`engine/`, PyO3 + maturin) que el backend invoca en proceso.

Base: plantilla RBAC (usuarios, roles, permisos, scoping, auditoría, JWT). Las reglas de negocio (conceptos, escalas por vigencia, tablas, parámetros) son datos configurables evaluados por el motor Rust. Referencias: `planillas_matriz/` (Excel actuales de la oficina) y el motor NG en `../varios/NG/decompilado/ns.nacional.sueldo*`. El plan de implementación vigente está en `~/.claude/plans/este-es-el-inicio-sleepy-quiche.md`.

**Estado:** Fases 0 a 4 completas para retiro y pensión con uno o más cargos (secuencias) y reglas de mayo 2022 en adelante. Pendiente: reajustes, acrecimientos, haberes devengados, reglas anteriores a 2022-05 (ver "Fuera de alcance" abajo). Alembic es la única fuente del esquema.

## Development Commands

### Backend (FastAPI)

**Setup:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Run development server:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Or use: ./run_dev.sh
```

**Initialize database (SQLAlchemy):**
```bash
cd backend
python -c "from app.db.init_db import create_tables, init_db; create_tables(); init_db()"
```

**Alembic migrations:**
```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

**Run tests:**
```bash
cd backend
pytest
pytest --cov=app
```

### Scaffold a new CRUD resource

`scripts/scaffold_resource.py` generates a full data model (backend + frontend) from
a YAML spec, following the `orders` reference pattern and its `TEMPLATE:<PLURAL>` sentinel
markers. See `scripts/scaffold/README.md` and `scripts/scaffold/specs/examples/`.

```bash
cd backend && ./venv/bin/pip install -r requirements-dev.txt   # jinja2 + pyyaml (dev only)
python scripts/scaffold_resource.py --from <spec>.yaml --dry-run
python scripts/scaffold_resource.py --from <spec>.yaml
python scripts/remove_domain.py <plural>          # undo (byte-clean round-trip)
python -m pytest scripts/scaffold/tests -q        # generator's own tests
```

`scoping.mode` = `none` / `own` / `attribute`. `Admin`/`Manager` roles auto-inherit new
resources via `init_db.py`. Not yet supported: `date`/`datetime` fields,
`grants.scoped_demo_roles`.

### Database (PostgreSQL)

```bash
./scripts/db-up.sh          # levanta PostgreSQL con docker compose
cd backend && alembic upgrade head && python -m app.db.init_db
```

**Database connection defaults:**
- Host: localhost:5432
- Database: otp_db
- User: otp_user
- Password: otp_password

## Architecture

### Backend Structure

The backend follows a layered architecture:

- **app/api/** - API endpoints organized by resource (auth, users, roles, permissions)
- **app/core/** - Core functionality (config, security, dependencies, `rbac.py` decision engine, `assertions.py` ABAC predicates)
- **app/models/** - SQLAlchemy ORM models
- **app/schemas/** - Pydantic schemas for validation
- **app/services/** - Business logic and CRUD operations
- **app/db/** - Database configuration and initialization

### RBAC Permission System

**Permission Format:** `resource:action` (e.g., `users:read`, `roles:create`). Wildcards
allowed: `users:*`, `*:read`, `*:*` (matched by `rbac.pattern_matches`).

**Decision engine:** `app/core/rbac.py` (pure, no FastAPI) builds an `EffectivePolicy`
(`allow` / `deny` / `conditional` pattern sets) per user and evaluates it:

- **Role hierarchy:** roles inherit from parent roles (table `role_parents`, DAG,
  cycle-guarded). `rbac.resolve_role_family` walks ancestors; a user's policy is the
  union over every assigned role's family.
- **DENY rules:** `role_permissions.effect` is `"allow"` (default) or `"deny"`. A matching
  `deny` always wins.
- **Assertions:** `role_permissions.assertion` names a predicate registered in
  `app/core/assertions.py` (built-in: `owner`). Evaluated at request time with a
  `context` dict supplied by the endpoint.
- **Data scoping ("which rows"):** `role_permissions.scope` is `"all"` (default),
  `"own"` or `"attribute"` (+ `scope_dimension`, e.g. `"warehouse"`). Values that place
  the user in a dimension live in table `user_scopes` (`user_id, dimension, value`).
  `rbac.resolve_scope(policy, resource, action, user) -> Scope`; the `Scope` object
  filters a query (`scope.apply(stmt, Model)`) and checks a loaded row
  (`scope.matches(row)`). `own` + `attribute` combine as OR; `deny` still wins;
  a plain `allow` (or superuser `*:*`) → `allow_all`.
- **Ternary result:** `rbac.evaluate(...) -> True | False | None`.
- **Cache:** `_policy_cache` (TTL 60s, key `(username, token_version)`); mutations
  (incl. `user_scopes` via `user_scope_service`) call `rbac.invalidate_policy_cache()`.

**Permission Checking:**
1. Superusers get the `{"*:*"}` policy (not a special code path).
2. Regular users inherit permissions from their roles and all ancestor roles.
3. `require_permissions(["users:read"])` — static dependency, no context (assertion-only
   rules do NOT grant here).
4. `has_permission(user, resource, action, *, db, context=...)` — full evaluation
   including assertions; call inside the endpoint body.
5. `require_scope("<resource>", "read")` — dependency returning `ScopedAccess(user, scope)`;
   403 only on `deny` / no rule. The endpoint applies `access.scope` to the query and to
   loaded rows.

**Example endpoint with permissions:**
```python
from app.core.deps import require_permissions, has_permission

@router.get("/users")
def list_users(current_user: User = Depends(require_permissions(["users:read"]))):
    ...

@router.get("/documents/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_active_user)):
    document = ...
    if not has_permission(current_user, "documents", "read", db=db,
                          context={"resource_owner_id": document.owner_id}):
        raise HTTPException(403)
```

**Role hierarchy API:** `POST /api/v1/roles/{id}/parents` (assign parents, 400 on cycle),
`GET /api/v1/roles/{id}/effective-permissions` (resolved allow/deny/conditional/scoped).
`POST /api/v1/roles/{id}/permissions` accepts either `permission_ids` or richer `rules`
(`{permission_id, effect, assertion, scope, scope_dimension}`).

**Scope admin API:** `GET/PUT /api/v1/users/{id}/scopes` and `GET /api/v1/users/me/scopes`
manage a user's `user_scopes` rows (`{items: [{dimension, value}]}`; PUT replaces the set).

**Convenience functions:** Use `require_user_read()`, `require_role_create()`, etc. from `app/core/deps.py` for common permission checks.

**Engine tests:** `cd backend && pytest` (see `tests/test_rbac_engine.py`,
`tests/test_roles_api.py`; SQLite in-memory, no live DB needed).

### Database Schema

The schema is defined by SQLModel models (`backend/app/models/`) and versioned only with Alembic migrations (`backend/alembic/versions/`). There are no native SQL scripts.

**Key relationships:**
- Users ↔ Roles (many-to-many via user_roles)
- Roles ↔ Permissions (many-to-many via role_permissions; carries `effect` + `assertion` +
  `scope` / `scope_dimension`)
- Roles ↔ Roles (many-to-many via role_parents; role hierarchy DAG)
- Users → scope values (`user_scopes`: `user_id, dimension, value`)

### Authentication Flow

1. Login via POST `/api/v1/auth/login` (form data `username`/`password`)
2. Receive JWT access token
3. Include token in requests: `Authorization: Bearer <token>`
4. Token verification happens in `app/core/deps.py:get_current_user()`

**Default Users:**
- superadmin/admin123 (Super Admin role)
- admin/admin123 (Admin role)
- manager/manager123 (Manager role)
- user/user123 (User role)

### Configuration

Environment variables are managed via `.env` file (see `.env.example`):
- Database connection settings (POSTGRES_*)
- JWT settings (SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES)
- CORS origins for frontend

Configuration is loaded via Pydantic Settings in `app/core/config.py`.

## Dominio previsional (Fase 1)

- **Modelos:** `backend/app/models/prevision.py` (`XBase` = campos editables y schema de entrada, `X` = tabla). Enums validados con `Annotated[str, StringConstraints(pattern=...)]` (SQLModel ignora `Field(regex=)`). Importes `Numeric(18,4)`; JSON/JSONB para `tablas.columnas`, `filas.valores`, `recibos.snapshot`.
- **CRUD:** `app/api/crud_router.py::make_crud_router` genera list/get/create/update/delete con permisos `<recurso>:<acción>`, paginación, filtros por query string y auditoría. Los recursos se declaran en la lista `RESOURCES` de `app/api/prevision.py` (con `guard` para inmutabilidad de liquidaciones CERRADAS). No usar `scaffold_resource.py` para estas tablas (no soporta fechas ni FKs).
- **Seed:** `app/db/init_prevision.py` crea los permisos y los roles Administrador, Liquidador, Consulta y Auditor (idempotente; lo invoca `init_db`).
- **Nuevo recurso:** modelo en `prevision.py` → entrada en `RESOURCES` → `alembic revision --autogenerate` (revisar que no arrastre operaciones ajenas y que importe `sqlmodel`) → entrada en `frontend/src/lib/resources.ts` (la página `ResourcePage.tsx` es genérica y se enruta sola).
- **Frontend:** `src/lib/resources.ts` describe columnas/campos/relaciones de cada recurso; `src/pages/ResourcePage.tsx` es la única página; el menú lateral toma `NAV_RESOURCE_KEYS`.
- **Deuda conocida de la plantilla:** `alembic check` reporta divergencias previas en `password_reset_tokens` y `role_parents`.

## Motor de fórmulas (Fase 2)

- Código en `engine/` (workspace Cargo: `otp-formula` núcleo + `otp-formula-py` binding PyO3). Referencia del lenguaje y contrato JSON: `engine/README.md`.
- Instalar en el venv del backend: `cd engine/otp-formula-py && maturin develop --release` (pip: `maturin`). Tests: `cd engine && cargo test`.
- Wrapper Python: `backend/app/services/motor.py`. Si `otp_engine` no está instalado el backend arranca igual, pero la validación de fórmulas se omite y `motor.calcular` lanza `MotorNoDisponible`; `tests/test_motor.py` y los tests de validación se saltean.
- Al crear/editar un concepto (`app/api/prevision.py::_validar_concepto`) se validan sintaxis, aridad, selectores y ciclos contra todos los conceptos activos → 422 con el detalle. `POST /api/v1/formulas/validar` valida una fórmula suelta.
- Regla de modelado: los conceptos derivados (pensión, art. 37) no deben estar en la columna que suma `TOTAL('COLUMNA')` del haber, o se forma un ciclo.

## Liquidación (Fases 3 y 4)

- **Flujo:** `POST /liquidaciones/{id}/calcular` → `services/liquidador.py::calcular_liquidacion`. Por recibo (retiro: uno; pensión: uno por beneficiario activo): parte el rango en tramos cada vez que cambia una regla (`ReglasDB.cortes`); en cada tramo, con las reglas vigentes al inicio, calcula **por cada cargo** la etapa `haber` (total remunerativo), pondera `HABER_PONDERADO = Σ total_cargo × porcentaje_secuencia/100` y calcula la etapa `beneficio` (`HABER_RETIRO`, `PENSION_TOTAL`, `PENSION_BENEFICIARIO`, `ART37`); importe = haber × meses comerciales (`services/retroactivo.py`, 30 días/mes), agrega SAC tras cada semestre completo (mitad del haber al cierre, proporcional a los meses trabajados) y calcula la etapa "liquidacion" (descuentos y anticipo sobre el subtotal). Persiste `recibos`, `recibo_conceptos`, `tramos_retroactivos` y los totales de la liquidación. Recalcular reemplaza; una liquidación CERRADA es inmutable (reabrir exige `liquidaciones:delete`).
- **Reglas como datos:** un concepto se aplica en una fecha si tiene una `ConceptoVigencia` vigente (general o por `tipo_beneficio`); un `#concepto` no asignado vale 0. Escalas = `Tabla` versionada por `vigencia_desde` (único por código+vigencia); porcentajes y montos = `ParametroHistorial`. Los conceptos del haber usan `decimales_importe=10` (la planilla no redondea pasos intermedios); los de "liquidacion", 2.
- **Variables que arma `services/reglas.py::variables_de_cargo`:** `CLASE`, `TIPO_PERSONAL`, `RESP_JERARQUICA_PORC`, `RECARGO_SERVICIO_PORC`, `TITULO`, `NIVEL_PREGRADO`, `RIESGO_ESPECIAL`, `ZONA_PORC`, `ZONA_CLASE`, `ANIOS_ANTIGUEDAD`, `CUERPO_APOYO_PORC`, `ADICIONAL_SEGURIDAD`, `PORCENTAJE_RETIRO_MANUAL`, y del beneficiario `PORCENTAJE`, `ART37`, `PARENTESCO`; en la etapa final `SUBTOTAL_CREDITO`, `ANTICIPO_IMPORTE`. Todos los porcentajes van de 0 a 100.
- **Dos cargos (secuencias):** cada `CargoSecuencia` lleva `porcentaje_secuencia` (DATOS "PORCENTAJE DE SECUENCIAS"); los cargos del causante deben sumar 100 y tener `secuencia` distinta (si no, 422). Con un cargo el peso es 100 y el resultado es el de siempre. El cargo de menor `secuencia` es el principal: de él salen `porcentaje_retiro` (manual) y `anios_antiguedad` para la tabla de % de retiro. `recibo_conceptos.secuencia` distingue el detalle de cada cargo (None = beneficio/liquidación). Etapas de concepto: `haber` (por tramo y cargo), `beneficio` (por tramo, sobre el haber ponderado) y `liquidacion` (una vez, sobre el subtotal).
- **Semilla de reglas:** `python -m app.db.seed_reglas [--force]` (no pisa lo editado sin `--force`). Las migraciones actualizan los conceptos sembrados cuando cambia su definición (p. ej. `e9f0a1b2c3d4` los movió a la etapa `beneficio`). Los datos (escalas, porcentajes, montos, qué conceptos existen cada mes) salen de las planillas con `scripts/import_reglas_planillas.py` → `backend/app/db/seed_data/reglas_planillas.json` (33 vigencias, 2022-05 a 2025-03; a partir de ahí rige la última). Las fórmulas están en `app/db/seed_reglas.py`.
- **Reportes:** `GET /liquidaciones/{id}/planilla.xlsx|pdf` (`services/reportes.py`). Frontend: `/liquidaciones/:id/planilla` (`pages/LiquidacionPlanilla.tsx`).
- **Paridad con Excel (Fase 4):** `tests/golden/casos_planilla.json` se genera con `python scripts/golden_planilla.py <xlsx convertido>`: carga cada caso en `DATOS`, recalcula la planilla original con LibreOffice y guarda los valores esperados (no salen del motor propio). `tests/test_golden_planillas.py` los compara mes por mes, SAC, subtotal, descuentos y líquido (4 casos: 3 retiros, 1 pensión con art. 37). Para dos cargos: `python scripts/golden_dos_cargos.py <BASE DE CALCULOS PENSION 2 CARGOS convertido>` → `tests/golden/casos_dos_cargos.json` (2 casos, hoja `LIQUIDACION `, jul/2022-dic/2024) y `tests/test_golden_dos_cargos.py`. Los helpers comunes están en `tests/golden_utils.py`. Para convertir el .xls: `soffice --headless --convert-to xlsx <archivo.xls>`.

### Supuestos a confirmar con la oficina técnico previsional
1. Tabla de % de retiro: 25 años → personal **subalterno**, 30 años → **superior** (`DATOS!J:K` y `M:N`); es una inferencia.
2. SAC: se calcula tras cada 30/06 y 31/12 dentro del rango; la planilla de ejemplo no lo muestra antes de dic/2015 y en semestres parciales usamos proporcional. Un parámetro `SAC_APLICA` no existe todavía.
3. Riesgo especial 6,5% (hasta 06/2024) y 13% (desde 07/2024) y título grado 20% / posgrado 25% salen de rótulos de `DATOS`; pensión 75%, art. 37 5%, descuentos (retiro 8% + OSEP 5% + 0,25% + 0,75%; pensión solo OSEP 6%) de las planillas de liquidación.
4. Anticipo en pensión con varios beneficiarios: se reparte proporcional al porcentaje.
5. Clase 19 no está en la escala vigente de la planilla (queda como error de cálculo explícito).
6. Con varios cargos, el % de retiro y los años para su tabla salen del cargo principal (secuencia menor); la planilla de dos cargos solo trae un % de retiro global. Los porcentajes de secuencia deben sumar exactamente 100 (la planilla muestra la suma en `DATOS!F68` pero no la valida).
7. En dos cargos, cada secuencia usa sus propios `anios_antiguedad` para el 2% por año de antigüedad; no está claro si en la práctica son años propios de la secuencia o la antigüedad final del causante.

### Errores detectados en la planilla original (no se replican)
- `B1 `: filas de feb y ago 2023 suman dos veces la misma celda (`='2023'!J68+'2023'!J68`).
- `B3`: filas de ene y feb 2023 apuntan a las columnas de mar y abr (`'2023'!O70`, `T70`).
- `B2!D122:D124` calculan el OSEP sobre `B3!F118` en lugar de su propio subtotal.
- `Pension Sin Coopart!A111` referencia el retiro (`'2025'!E45`) y no la pensión (`E46`).
- Fechas de texto inválidas en `Planilla Retiro` (`31/04/2014`, `31/06/2020`) y `31/11/2024` en `LIQUIDACION `.
- **Planilla de 2 cargos:** las hojas `B1`/`B2` tienen el subtotal roto (`=SUM(#REF!)`); la base de zona (concepto 83) quedó con la escala vieja en abr-may/2023 y con un valor mal tipeado en jul/2024 (clase 5); "Aumento Marzo/2010" quedó en 8110,48 en nov/2024 (correcto: 8345,57). `scripts/golden_dos_cargos.py` corrige esas celdas en la copia de trabajo y las informa en el JSON.

### Fuera de alcance por ahora
Reajustes y acrecimientos, haberes devengados y no percibidos, anticipos con cooparticipes, reglas anteriores a 2022-05 (el importador y el modelo lo soportan; falta cargar/verificar las hojas antiguas, cuyo formato difiere), cálculo automático de zona y de antigüedad final desde los períodos de servicio.

## Key Design Patterns

**Dependency Injection:** FastAPI's `Depends()` is used throughout for database sessions, authentication, and authorization.

**Permission Inheritance:** Users inherit all permissions from their assigned roles. The `require_permissions()` function collects permissions from all active roles assigned to a user.

**Database Sessions:** Always use `db: Session = Depends(get_db)` to get database sessions. Sessions are automatically closed after the request.

**Password Hashing:** Passwords are hashed using bcrypt via `passlib`. Use `get_password_hash()` and `verify_password()` from `app/core/security.py`.

## API Endpoints

All endpoints are prefixed with `/api/v1`:

- **Auth:** `/auth/login`
- **Users:** `/users/` (CRUD + `/users/me` for current user + `/users/{id}/scopes`)
- **Roles:** `/roles/` (CRUD + `/roles/{id}/permissions` to assign permissions)
- **Permissions:** `/permissions/` (CRUD)

API documentation available at `http://localhost:8000/docs` when running.

## Important Notes

- `frontend/` is a React 19 + Vite + Tailwind v4 SPA (`npm run dev` / `npm run build`).
  Pages under `src/pages/`, API layer `src/lib/api/services.ts`, auth in `src/context/AuthContext.tsx`.
  The Roles page has a per-permission rule editor (effect + scope); Users has a `user_scopes`
  editor.
- Always change default passwords and SECRET_KEY before deploying to production.
