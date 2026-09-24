import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import { Shield } from 'lucide-react';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const { success } = useToast();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login({ username, password });
      success(`¡Bienvenido ${username}!`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesión');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-stone-900 dark:bg-stone-100 mb-4">
            <Shield className="w-6 h-6 text-white dark:text-stone-900" />
          </div>
          <h1 className="text-xl font-semibold text-stone-900 dark:text-stone-100">online-otp</h1>
          <p className="text-sm text-stone-400 dark:text-stone-500 mt-1">Control de acceso basado en roles</p>
        </div>

        {/* Form card */}
        <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900/50 px-3 py-2.5 rounded-md">
                {error}
              </div>
            )}

            <Input
              label="Usuario"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="nombre de usuario"
              required
              autoComplete="username"
            />

            <Input
              label="Contraseña"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />

            <Button
              type="submit"
              fullWidth
              disabled={isLoading}
              className="mt-2"
            >
              {isLoading ? 'Verificando...' : 'Iniciar sesión'}
            </Button>

            <div className="text-center pt-1">
              <Link
                to="/forgot-password"
                className="text-xs text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 transition-colors"
              >
                ¿Olvidaste tu contraseña?
              </Link>
            </div>
          </form>
        </div>

        {/* Test credentials */}
        <div className="mt-4 px-4 py-3 bg-stone-100 dark:bg-stone-900/60 rounded-lg border border-stone-200 dark:border-stone-800">
          <p className="text-xs font-medium text-stone-500 dark:text-stone-400 mb-2">Credenciales de prueba</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {[
              ['superadmin', 'admin123'],
              ['admin', 'admin123'],
              ['manager', 'manager123'],
              ['user', 'user123'],
            ].map(([u, p]) => (
              <button
                key={u}
                type="button"
                onClick={() => { setUsername(u); setPassword(p); }}
                className="text-left text-xs text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200 transition-colors py-0.5"
              >
                <span className="font-medium text-stone-700 dark:text-stone-300">{u}</span>
                <span className="text-stone-400 dark:text-stone-600"> / {p}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
