// User types
export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at?: string;
  roles: Role[];
}

// Role types
export interface Role {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
  permissions: Permission[];
}

// Permission types
export interface Permission {
  id: number;
  name: string;
  description: string;
  resource: string;
  action: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

// Rule / scoping types
export type RuleEffect = 'allow' | 'deny';
export type RuleScope = 'all' | 'own' | 'attribute';

export interface PermissionRule {
  permission_id: number;
  effect: RuleEffect;
  assertion?: string | null;
  scope: RuleScope;
  scope_dimension?: string | null;
}

export interface EffectivePermissions {
  role_id: number;
  contributing_role_ids: number[];
  allow: string[];
  deny: string[];
  conditional: { pattern: string; assertion: string }[];
  scoped: { pattern: string; scope: RuleScope; dimension: string | null }[];
}

export interface UserScope {
  dimension: string;
  value: string;
}


// AuditLog types
export interface AuditLog {
  id: number;
  user_id: number | null;
  username: string | null;
  action: string;
  resource: string;
  resource_id: number | null;
  details: string | null;
  ip_address: string | null;
  request_id: string | null;
  status: string;
  before_data: string | null;
  after_data: string | null;
  subject_id: number | null;
  user_agent: string | null;
  timestamp: string | null;
}

// Auth types
export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthContextType {
  user: User | null;
  setUser: (user: User | null) => void;
  token: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
}

// API Response types
export interface ApiError {
  detail: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// CRUD DTOs
export interface CreateUserDTO {
  username: string;
  email: string;
  password: string;
  full_name: string;
  is_active?: boolean;
  role_ids?: number[];
}

export interface UpdateUserDTO {
  email?: string;
  full_name?: string;
  is_active?: boolean;
  password?: string;
}

export interface UpdateProfileDTO {
  email?: string;
  full_name?: string;
}

export interface ChangePasswordDTO {
  current_password: string;
  new_password: string;
}

export interface CreateRoleDTO {
  name: string;
  description: string;
  is_active?: boolean;
  permission_ids?: number[];
}

export interface UpdateRoleDTO {
  name?: string;
  description?: string;
  is_active?: boolean;
}

export interface CreatePermissionDTO {
  name: string;
  description: string;
  resource: string;
  action: string;
  is_active?: boolean;
}

export interface UpdatePermissionDTO {
  name?: string;
  description?: string;
  is_active?: boolean;
}

// Query param types
export interface GetUsersParams {
  page?: number;
  size?: number;
  search?: string;
  is_active?: boolean;
}

export interface GetRolesParams {
  page?: number;
  size?: number;
  search?: string;
  is_active?: boolean;
}

export interface GetPermissionsParams {
  page?: number;
  size?: number;
  search?: string;
  resource?: string;
  action?: string;
  is_active?: boolean;
}

export interface GetAuditLogsParams {
  page?: number;
  size?: number;
  user_id?: number;
  action?: string;
  resource?: string;
  status?: string;
  from_date?: string;
  to_date?: string;
}

// Component props types
export interface ProtectedComponentProps {
  permissions?: string[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export interface TableColumn<T> {
  key: keyof T | string;
  label: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
}

export interface TableAction<T> {
  label: string;
  onClick: (item: T) => void;
  icon?: React.ReactNode;
  permission?: string;
  variant?: 'primary' | 'secondary' | 'danger';
}

// Password reset DTOs
export interface PasswordResetRequestDTO {
  identifier: string;
}

export interface PasswordResetConfirmDTO {
  token: string;
  new_password: string;
}
