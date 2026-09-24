# Changelog - Frontend RBAC Application

## [1.2.0] - 2026-09-02

### ✨ Alcance de datos (data scoping)

- **Roles** (`pages/Roles.tsx`): el asignador de permisos pasó de checkboxes planos a un
  **editor de reglas** por permiso — `effect` (permitir / denegar) y `scope`
  (todos / propios / por atributo + dimensión). Nueva acción **"Permisos efectivos"**
  (`components/roles/EffectivePermissionsModal.tsx`) que muestra allow / deny / condicionales /
  acotados resueltos sobre la jerarquía.
- **Usuarios** (`pages/Users.tsx`): nueva acción **"Alcances de datos"**
  (`components/users/UserScopesModal.tsx`) para gestionar las filas `user_scopes`
  (pares dimensión = valor, ej. `warehouse = norte`).
- **Pedidos** (`pages/Orders.tsx`, ruta `/orders`, ítem de sidebar): página CRUD del modelo
  de dominio de ejemplo. La lista llega ya filtrada por el alcance del usuario; banner que
  explica el filtrado y muestra los alcances propios (`GET /users/me/scopes`).
- **API** (`lib/api/services.ts`): `roleService.assignPermissionRules` / `getPermissionRules` /
  `getEffectivePermissions`; `userService.getScopes` / `setScopes` / `getMyScopes`;
  `orderService` (CRUD). Tipos nuevos en `types/index.ts`, opciones en `lib/constants.ts`.
- **Auditoría** (`pages/Audit.tsx`): filtros para recurso `order` y acciones
  `set_scopes` / `assign_parents`.

## [1.1.0] - 2025-01-08

### ✨ Nuevas Características

#### Sistema de Notificaciones Toast
- **Componentes creados:**
  - `context/ToastContext.tsx` - Context provider para gestión de toasts
  - `components/common/ToastContainer.tsx` - Container para renderizar toasts

- **Características:**
  - 4 tipos de notificaciones: success, error, warning, info
  - Auto-dismiss configurable (por defecto 5s para info/success/warning, 7s para error)
  - Animaciones suaves de entrada/salida
  - Stack de notificaciones en esquina superior derecha
  - Cierre manual de notificaciones

- **API de uso:**
  ```tsx
  const { success, error, warning, info } = useToast();

  success('Operación completada');
  error('Error al procesar');
  warning('Advertencia importante');
  info('Información adicional');
  ```

#### Modal de Confirmación
- **Componentes creados:**
  - `components/common/ConfirmDialog.tsx` - Modal de confirmación
  - `lib/hooks/useConfirm.tsx` - Hook personalizado para confirmaciones

- **Características:**
  - Reemplaza `alert()` y `confirm()` nativos del navegador
  - Diseño moderno y consistente
  - 3 variantes: danger (rojo), warning (amarillo), info (azul)
  - Promise-based para mejor control de flujo asíncrono

- **API de uso:**
  ```tsx
  const { confirm, ConfirmationDialog } = useConfirm();

  const confirmed = await confirm({
    title: 'Eliminar Usuario',
    message: '¿Está seguro? Esta acción no se puede deshacer.',
    confirmText: 'Eliminar',
    cancelText: 'Cancelar',
    variant: 'danger'
  });

  if (confirmed) {
    // Proceder con la acción
  }

  // Agregar al JSX
  <ConfirmationDialog />
  ```

### 🔄 Mejoras Aplicadas

#### Página de Usuarios (`app/dashboard/users/page.tsx`)
- ✅ Toast de éxito al crear usuario
- ✅ Toast de éxito al actualizar usuario
- ✅ Toast de éxito al eliminar usuario
- ✅ Toast de error en operaciones fallidas
- ✅ Modal de confirmación para eliminación
- ✅ Mejor feedback visual en todas las operaciones

#### Página de Roles (`app/dashboard/roles/page.tsx`)
- ✅ Toast de éxito al crear rol
- ✅ Toast de éxito al actualizar rol
- ✅ Toast de éxito al eliminar rol
- ✅ Toast de error en operaciones fallidas
- ✅ Modal de confirmación para eliminación
- ✅ Mejor feedback visual en todas las operaciones

#### Página de Permisos (`app/dashboard/permissions/page.tsx`)
- ✅ Toast de éxito al crear permiso
- ✅ Toast de éxito al actualizar permiso
- ✅ Toast de éxito al eliminar permiso
- ✅ Toast de error en operaciones fallidas
- ✅ Modal de confirmación para eliminación
- ✅ Mejor feedback visual en todas las operaciones

#### Página de Login (`app/login/page.tsx`)
- ✅ Toast de bienvenida al iniciar sesión exitosamente
- ✅ Mantiene el error inline para credenciales inválidas

### 🎨 Mejoras de UI/UX

#### Animaciones
- Animación `slide-in-right` para toasts
- Transiciones suaves en modales
- Feedback visual inmediato en todas las acciones

#### Consistencia
- Todos los mensajes de éxito/error ahora usan el mismo sistema
- Eliminados todos los `alert()` y `confirm()` nativos
- Diseño uniforme en toda la aplicación

### 🔧 Cambios Técnicos

#### Nuevas Dependencias de Context
- `ToastProvider` - Debe envolver la aplicación (ya integrado en layout)
- Providers anidados: `ToastProvider` → `AuthProvider`

#### CSS Personalizado
- Nueva animación `@keyframes slide-in-right` en `globals.css`
- Clase utility `.animate-slide-in-right`

### 📝 Próximas Mejoras Planificadas

1. **Validación de Formularios**
   - Validación en tiempo real
   - Mensajes de error específicos por campo

2. **Loading Skeletons**
   - Skeleton loaders para tablas
   - Mejor experiencia durante la carga

3. **Búsqueda y Filtros**
   - Búsqueda en tiempo real
   - Filtros por estado, rol, etc.
   - Ordenamiento de columnas

4. **Paginación**
   - Paginación del lado del cliente
   - Selector de items por página

5. **Perfil de Usuario**
   - Página de perfil personal
   - Edición de datos propios

6. **Auditoría**
   - Viewer de logs
   - Filtros avanzados

7. **Modo Oscuro**
   - Theme switcher
   - Persistencia de preferencia

### 🐛 Fixes

- Corregido el envío de `user_id` y `role_id` en requests de asignación
- Mejorado el manejo de errores en todas las operaciones CRUD

---

## Instrucciones de Uso

### Para desarrolladores que continúen el proyecto:

1. **Usar Toasts:**
   ```tsx
   import { useToast } from '@/context/ToastContext';

   const { success, error, warning, info } = useToast();
   success('Mensaje de éxito');
   ```

2. **Usar Confirmaciones:**
   ```tsx
   import { useConfirm } from '@/lib/hooks/useConfirm';

   const { confirm, ConfirmationDialog } = useConfirm();

   const confirmed = await confirm({
     title: 'Título',
     message: 'Mensaje',
     variant: 'danger'
   });

   // No olvidar agregar al final del JSX
   return (
     <>
       {/* ... contenido */}
       <ConfirmationDialog />
     </>
   );
   ```

### Convenciones:
- Usar toasts para feedback de operaciones CRUD
- Usar confirmaciones para acciones destructivas
- Mensajes concisos y claros
- Variante `danger` para eliminaciones
- Variante `warning` para cambios importantes
- Variante `info` para información general
