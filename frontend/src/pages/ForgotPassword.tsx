import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Shield, ArrowLeft, Mail } from 'lucide-react';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import { authService } from '@/lib/api/services';

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await authService.requestPasswordReset({ identifier });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al procesar la solicitud');
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
          {submitted ? (
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-50 dark:bg-emerald-950/40 mb-2">
                <Mail className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
              </div>
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">Revisá tu correo</h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">
                Si el usuario existe, recibirás un correo con instrucciones para restablecer tu contraseña. El enlace expira en 30 minutos.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-xs text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-200 transition-colors mt-2"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Volver al inicio de sesión
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-5">
                <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">Recuperar contraseña</h2>
                <p className="text-xs text-stone-500 dark:text-stone-400 mt-1">
                  Ingresá tu email o nombre de usuario y te enviaremos instrucciones.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900/50 px-3 py-2.5 rounded-md">
                    {error}
                  </div>
                )}

                <Input
                  label="Email o nombre de usuario"
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="usuario@empresa.com"
                  required
                  autoComplete="email"
                />

                <Button
                  type="submit"
                  fullWidth
                  disabled={isLoading || !identifier.trim()}
                  className="mt-2"
                >
                  {isLoading ? 'Enviando...' : 'Enviar instrucciones'}
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
