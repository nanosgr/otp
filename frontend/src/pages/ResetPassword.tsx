import { useState, FormEvent, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Shield, ArrowLeft, CheckCircle } from 'lucide-react';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import { authService } from '@/lib/api/services';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') ?? '';

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      navigate('/forgot-password', { replace: true });
    }
  }, [token, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }
    if (newPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres');
      return;
    }

    setIsLoading(true);
    try {
      await authService.confirmPasswordReset({ token, new_password: newPassword });
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'El enlace es inválido o ya expiró');
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

        <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-6 shadow-sm">
          {success ? (
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/40 mb-2">
                <CheckCircle className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
              </div>
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
                Contraseña actualizada
              </h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">
                Tu contraseña fue cambiada correctamente. Ya podés iniciar sesión con tu nueva contraseña.
              </p>
              <Link to="/login">
                <Button fullWidth className="mt-2">
                  Ir al inicio de sesión
                </Button>
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-5">
                <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">Nueva contraseña</h2>
                <p className="text-xs text-stone-500 dark:text-stone-400 mt-1">
                  Elegí una contraseña segura de al menos 8 caracteres.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900/50 px-3 py-2.5 rounded-md">
                    {error}
                  </div>
                )}

                <Input
                  label="Nueva contraseña"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  required
                  autoComplete="new-password"
                />

                <Input
                  label="Confirmar contraseña"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repetí la contraseña"
                  required
                  autoComplete="new-password"
                  error={confirmPassword && newPassword !== confirmPassword ? 'Las contraseñas no coinciden' : undefined}
                />

                <Button
                  type="submit"
                  fullWidth
                  disabled={isLoading || !newPassword || !confirmPassword}
                  className="mt-2"
                >
                  {isLoading ? 'Guardando...' : 'Cambiar contraseña'}
                </Button>
              </form>

              <div className="text-center mt-4">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-xs text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Volver al inicio de sesión
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
