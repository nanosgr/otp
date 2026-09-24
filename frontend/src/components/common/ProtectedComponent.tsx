import { useAuth } from '@/context/AuthContext';
import { ProtectedComponentProps } from '@/types';

export default function ProtectedComponent({
  permissions = [],
  requireAll = false,
  fallback = null,
  children,
}: ProtectedComponentProps) {
  const { hasAllPermissions, hasAnyPermission } = useAuth();

  if (permissions.length === 0) {
    return <>{children}</>;
  }

  const hasAccess = requireAll
    ? hasAllPermissions(permissions)
    : hasAnyPermission(permissions);

  if (!hasAccess) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
