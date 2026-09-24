# online-otp - Frontend

Frontend de la aplicación RBAC construido con Next.js 15, TypeScript y Tailwind CSS.

## Características

- ✅ Autenticación con JWT
- ✅ Dashboard responsivo con estadísticas
- ✅ CRUD completo de Usuarios, Roles y Permisos
- ✅ Control de acceso basado en permisos
- ✅ Componentes condicionales según permisos del usuario
- ✅ Diseño moderno y responsivo
- ✅ TypeScript para type safety

## Requisitos

- Node.js 18.18.0+
- npm o yarn
- Backend corriendo en http://localhost:8000

## Instalación

1. **Instalar dependencias:**
   ```bash
   npm install
   ```

2. **Configurar variables de entorno:**
   ```bash
   cp .env.local.example .env.local
   ```

   Editar `.env.local` si es necesario:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```

## Desarrollo

**Ejecutar servidor de desarrollo:**
```bash
npm run dev
```

La aplicación estará disponible en http://localhost:3000

## Estructura del Proyecto

```
frontend/
├── app/                      # App Router de Next.js
│   ├── dashboard/           # Páginas del dashboard
│   │   ├── users/          # Gestión de usuarios
│   │   ├── roles/          # Gestión de roles
│   │   └── permissions/    # Gestión de permisos
│   ├── login/              # Página de login
│   └── layout.tsx          # Layout principal
├── components/              # Componentes React
│   ├── common/             # Componentes reutilizables
│   └── layout/             # Componentes de layout
├── context/                # Context providers
├── lib/                    # Librerías y utilidades
└── types/                  # Definiciones de TypeScript
```

## Funcionalidades Principales

### Autenticación
- Login con usuario y contraseña
- Almacenamiento seguro de JWT
- Auto-logout cuando el token expira

### Control de Permisos
El sistema usa el componente `ProtectedComponent`:

```tsx
<ProtectedComponent permissions={['users:create']}>
  <Button onClick={handleCreate}>Crear Usuario</Button>
</ProtectedComponent>
```

### Gestión de Usuarios, Roles y Permisos
- CRUD completo con validación de permisos
- Asignación dinámica de roles y permisos
- Vista agrupada por recurso

## Usuarios de Prueba

| Usuario    | Contraseña | Descripción |
|------------|------------|-------------|
| superadmin | admin123   | Acceso total |
| admin      | admin123   | Acceso administrativo |
| manager    | manager123 | Acceso de gestión |
| user       | user123    | Acceso básico |

## Build para Producción

```bash
npm run build
npm start
```

## Tecnologías

- Next.js 15 - Framework React
- TypeScript - Type safety
- Tailwind CSS - Estilos
- React Context - State management
