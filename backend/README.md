# online-otp Backend

Sistema de autenticación y autorización basado en roles (RBAC) construido con FastAPI.

## Características

- 🔐 Autenticación JWT
- 👥 Gestión de usuarios
- 🎭 Sistema de roles
- 🔑 Sistema de permisos granular
- 🛡️ Middleware de autorización
- 📚 Documentación automática con Swagger
- 🗄️ Base de datos PostgreSQL
- 🔄 Migraciones con Alembic

## Estructura del Proyecto

```
backend/
├── app/
│   ├── api/                 # Endpoints de la API
│   │   ├── auth.py         # Autenticación
│   │   ├── users.py        # Gestión de usuarios
│   │   ├── roles.py        # Gestión de roles
│   │   └── permissions.py  # Gestión de permisos
│   ├── core/               # Configuración central
│   │   ├── config.py       # Configuración de la app
│   │   ├── security.py     # Funciones de seguridad
│   │   └── deps.py         # Dependencias y auth
│   ├── db/                 # Base de datos
│   │   ├── database.py     # Configuración DB
│   │   └── init_db.py      # Inicialización
│   ├── models/             # Modelos SQLAlchemy
│   ├── schemas/            # Esquemas Pydantic
│   ├── services/           # Lógica de negocio
│   └── main.py            # Aplicación FastAPI
├── alembic/               # Migraciones
├── requirements.txt       # Dependencias
└── .env                  # Variables de entorno
```

## Instalación

### Prerequisitos

- Python 3.8+
- PostgreSQL 12+
- pip

### Configuración Rápida

1. **Ejecutar el script de configuración:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

### Configuración Manual

1. **Crear entorno virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar PostgreSQL:**
   ```bash
   # Crear base de datos
   createdb rbac_db
   ```

4. **Configurar variables de entorno:**
   ```bash
   cp .env.example .env
   # Editar .env con tus configuraciones
   ```

5. **Inicializar base de datos:**
   ```bash
   python -c "from app.db.init_db import create_tables, init_db; create_tables(); init_db()"
   ```

## Uso

### Ejecutar servidor de desarrollo

```bash
# Opción 1: Script automático
./run_dev.sh

# Opción 2: Comando directo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Acceder a la aplicación

- **API**: http://localhost:8000
- **Documentación Swagger**: http://localhost:8000/docs
- **Documentación ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Usuarios por Defecto

El sistema se inicializa con los siguientes usuarios:

| Usuario    | Contraseña | Rol          | Descripción           |
|------------|------------|--------------|----------------------|
| superadmin | admin123   | Super Admin  | Acceso completo      |
| admin      | admin123   | Admin        | Acceso administrativo |
| manager    | manager123 | Manager      | Acceso de gestión    |
| user       | user123    | User         | Acceso básico        |

## Estructura RBAC

### Roles Predefinidos

1. **Super Admin**: Acceso completo al sistema
2. **Admin**: Acceso administrativo (sin eliminar permisos críticos)
3. **Manager**: Permisos de lectura y algunos de escritura
4. **User**: Acceso básico a dashboard y reportes
5. **Viewer**: Solo permisos de lectura

### Permisos por Recurso

- **users**: create, read, update, delete
- **roles**: create, read, update, delete
- **permissions**: create, read, update, delete
- **dashboard**: read
- **reports**: read, export
- **settings**: read, update

## API Endpoints

### Autenticación
- `POST /api/v1/auth/login` - Login con form data
- `POST /api/v1/auth/login-json` - Login con JSON

### Usuarios
- `GET /api/v1/users/` - Listar usuarios
- `POST /api/v1/users/` - Crear usuario
- `GET /api/v1/users/me` - Usuario actual
- `GET /api/v1/users/{id}` - Obtener usuario
- `PUT /api/v1/users/{id}` - Actualizar usuario
- `DELETE /api/v1/users/{id}` - Eliminar usuario
- `POST /api/v1/users/{id}/roles` - Asignar roles

### Roles
- `GET /api/v1/roles/` - Listar roles
- `POST /api/v1/roles/` - Crear rol
- `GET /api/v1/roles/{id}` - Obtener rol
- `PUT /api/v1/roles/{id}` - Actualizar rol
- `DELETE /api/v1/roles/{id}` - Eliminar rol
- `POST /api/v1/roles/{id}/permissions` - Asignar permisos

### Permisos
- `GET /api/v1/permissions/` - Listar permisos
- `POST /api/v1/permissions/` - Crear permiso
- `GET /api/v1/permissions/{id}` - Obtener permiso
- `PUT /api/v1/permissions/{id}` - Actualizar permiso
- `DELETE /api/v1/permissions/{id}` - Eliminar permiso

## Migraciones con Alembic

```bash
# Crear migración
alembic revision --autogenerate -m "Descripción del cambio"

# Aplicar migraciones
alembic upgrade head

# Ver historial
alembic history

# Revertir migración
alembic downgrade -1
```

## Desarrollo

### Estructura de Permisos

Los permisos siguen el formato `recurso:acción`:
- `users:read` - Leer usuarios
- `roles:create` - Crear roles
- `permissions:delete` - Eliminar permisos

### Agregar Nuevos Endpoints

1. Crear el endpoint en el archivo apropiado en `app/api/`
2. Agregar decorador de permisos:
   ```python
   @router.get("/nuevo-endpoint")
   def nuevo_endpoint(
       current_user: User = Depends(require_permissions(["recurso:accion"]))
   ):
       pass
   ```

### Variables de Entorno

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| PROJECT_NAME | Nombre del proyecto | "online-otp" |
| SECRET_KEY | Clave secreta JWT | (cambiar en producción) |
| DATABASE_URL | URL de PostgreSQL | Auto-generada |
| ACCESS_TOKEN_EXPIRE_MINUTES | Expiración token | 30 |

## Testing

```bash
# Ejecutar tests (cuando estén implementados)
pytest

# Con cobertura
pytest --cov=app
```

## Producción

1. Cambiar `SECRET_KEY` en `.env`
2. Configurar base de datos de producción
3. Usar servidor WSGI como Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

## Contribuir

1. Fork el proyecto
2. Crear branch para feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push al branch (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

Este proyecto está bajo la licencia MIT.
