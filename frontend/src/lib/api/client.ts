import { AuthResponse } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

function formatDetail(detail: unknown): string {
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === 'object' && 'msg' in d ? `${((d as { loc?: unknown[] }).loc ?? []).slice(-1)[0] ?? ''}: ${(d as { msg: string }).msg}` : String(d)))
      .join('; ');
  }
  return typeof detail === 'string' ? detail : '';
}

class ApiClient {
  private baseURL: string;
  private token: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing = false;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('token');
      this.refreshToken = localStorage.getItem('refresh_token');
    }
  }

  setToken(token: string | null) {
    this.token = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('token', token);
      } else {
        localStorage.removeItem('token');
      }
    }
  }

  getToken(): string | null {
    return this.token;
  }

  setRefreshToken(token: string | null) {
    this.refreshToken = token;
    if (typeof window !== 'undefined') {
      if (token) {
        localStorage.setItem('refresh_token', token);
      } else {
        localStorage.removeItem('refresh_token');
      }
    }
  }

  getRefreshToken(): string | null {
    return this.refreshToken;
  }

  private async attemptRefresh(): Promise<boolean> {
    // Serializa múltiples peticiones concurrentes en un solo intento de refresh
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    this.isRefreshing = true;
    this.refreshPromise = (async () => {
      const storedRefresh = this.refreshToken;
      if (!storedRefresh) return false;
      try {
        const response = await fetch(`${this.baseURL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: storedRefresh }),
        });
        if (!response.ok) return false;
        const data: AuthResponse = await response.json();
        this.setToken(data.access_token);
        this.setRefreshToken(data.refresh_token);
        return true;
      } catch {
        return false;
      }
    })().finally(() => {
      this.isRefreshing = false;
      this.refreshPromise = null;
    });

    return this.refreshPromise;
  }

  private expireSession() {
    this.setToken(null);
    this.setRefreshToken(null);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('auth:expired'));
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const buildHeaders = (token: string | null): HeadersInit => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string>),
      };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      return headers;
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: buildHeaders(this.token),
    });

    // Intenta refresh si recibe 401 y no es el propio endpoint de refresh
    if (response.status === 401 && !endpoint.includes('/auth/')) {
      const refreshed = await this.attemptRefresh();
      if (!refreshed) {
        this.expireSession();
        throw new Error('Sesión expirada. Por favor inicia sesión nuevamente.');
      }
      // Reintenta la petición original con el nuevo access token
      const retryResponse = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: buildHeaders(this.token),
      });
      if (!retryResponse.ok) {
        const error = await retryResponse.json().catch(() => ({ detail: 'An error occurred' }));
        throw new Error(formatDetail(error.detail) || `HTTP ${retryResponse.status}`);
      }
      if (retryResponse.status === 204) return undefined as T;
      return retryResponse.json();
    }

    if (!response.ok) {
      if (response.status === 403) {
        const error = await response.json().catch(() => ({ detail: 'No tienes permiso para realizar esta acción' }));
        const err = new Error(error.detail || 'No tienes permiso para realizar esta acción') as Error & { status: number };
        err.status = 403;
        throw err;
      }
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
      throw new Error(formatDetail(error.detail) || `HTTP ${response.status}`);
    }

    if (response.status === 204) return undefined as T;
    return response.json();
  }

  /** Descarga un archivo (con autenticación y reintento tras refresh) y devuelve el Blob. */
  async download(endpoint: string): Promise<Blob> {
    const send = () => fetch(`${this.baseURL}${endpoint}`, {
      headers: this.token ? { Authorization: `Bearer ${this.token}` } : {},
    });
    let response = await send();
    if (response.status === 401) {
      if (!(await this.attemptRefresh())) {
        this.expireSession();
        throw new Error('Sesión expirada. Por favor inicia sesión nuevamente.');
      }
      response = await send();
    }
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(formatDetail((error as { detail?: unknown }).detail) || `HTTP ${response.status}`);
    }
    return response.blob();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  async login(username: string, password: string): Promise<AuthResponse> {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(`${this.baseURL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Invalid credentials' }));
      throw new Error(error.detail || 'Authentication failed');
    }

    const data: AuthResponse = await response.json();
    this.setToken(data.access_token);
    this.setRefreshToken(data.refresh_token);
    return data;
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
