import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/lib/api/client';
import { userService } from '@/lib/api/services';
import { AuthContextType, LoginCredentials, User } from '@/types';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  const logout = useCallback(() => {
    apiClient.setToken(null);
    apiClient.setRefreshToken(null);
    setUser(null);
    setTokenState(null);
    navigate('/login');
  }, [navigate]);

  useEffect(() => {
    const handleExpired = () => logout();
    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, [logout]);

  useEffect(() => {
    const loadUser = async () => {
      const savedToken = apiClient.getToken();
      if (savedToken) {
        try {
          const userData = await userService.getMe();
          setUser(userData);
          setTokenState(savedToken);
        } catch {
          apiClient.setToken(null);
          apiClient.setRefreshToken(null);
        }
      }
      setIsLoading(false);
    };

    loadUser();
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const response = await apiClient.login(credentials.username, credentials.password);
    setTokenState(response.access_token);
    const userData = await userService.getMe();
    setUser(userData);
    navigate('/dashboard');
  }, [navigate]);

  const hasPermission = useCallback((permission: string): boolean => {
    if (!user) return false;
    if (user.is_superuser) return true;
    const [resource, action] = permission.split(':');
    // Coincidencia con comodines, igual que rbac.pattern_matches del backend:
    // `*:*`, `users:*` y `*:read` deben conceder el permiso.
    const matches = (p: { resource: string; action: string }) =>
      (p.resource === '*' || p.resource === resource) &&
      (p.action === '*' || p.action === action);
    return user.roles.some(
      (role) =>
        role.is_active &&
        role.permissions.some((p) => p.is_active && matches(p))
    );
  }, [user]);

  const hasAnyPermission = useCallback(
    (permissions: string[]): boolean => permissions.some(hasPermission),
    [hasPermission]
  );

  const hasAllPermissions = useCallback(
    (permissions: string[]): boolean => permissions.every(hasPermission),
    [hasPermission]
  );

  const value: AuthContextType = {
    user,
    setUser,
    token,
    login,
    logout,
    isAuthenticated: !!user,
    isLoading,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
