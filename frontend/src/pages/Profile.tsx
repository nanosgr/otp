import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { userService } from '@/lib/api/services';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import UserAvatar from '@/components/common/UserAvatar';
import ErrorAlert from '@/components/common/ErrorAlert';
import { UpdateProfileDTO, ChangePasswordDTO } from '@/types';
import { Pencil, Save, X, Lock, ShieldCheck } from 'lucide-react';

export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const { success } = useToast();

  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profileData, setProfileData] = useState<UpdateProfileDTO>({
    full_name: user?.full_name ?? '',
    email: user?.email ?? '',
  });
  const [profileError, setProfileError] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  const [passwordData, setPasswordData] = useState<ChangePasswordDTO & { confirm: string }>({
    current_password: '',
    new_password: '',
    confirm: '',
  });
  const [passwordError, setPasswordError] = useState('');
  const [isSavingPwd, setIsSavingPwd] = useState(false);

  useEffect(() => {
    if (user) {
      setProfileData({ full_name: user.full_name, email: user.email });
    }
  }, [user]);

  if (!user) {
    return <DashboardLayout title="Mi Perfil"><Card><p className="text-stone-500 dark:text-stone-400">Cargando...</p></Card></DashboardLayout>;
  }

  const handleProfileSubmit = async () => {
    setProfileError('');
    if (!profileData.email) { setProfileError('El email es obligatorio'); return; }
    setIsSavingProfile(true);
    try {
      const updatedUser = await userService.updateMe(profileData);
      setUser(updatedUser);
      setIsEditingProfile(false);
      success('Perfil actualizado correctamente');
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : 'Error al actualizar el perfil');
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handlePasswordSubmit = async () => {
    setPasswordError('');
    if (!passwordData.current_password || !passwordData.new_password || !passwordData.confirm) {
      setPasswordError('Todos los campos son obligatorios');
      return;
    }
    if (passwordData.new_password !== passwordData.confirm) {
      setPasswordError('Las contraseñas nuevas no coinciden');
      return;
    }
    if (passwordData.new_password.length < 8) {
      setPasswordError('La nueva contraseña debe tener al menos 8 caracteres');
      return;
    }
    setIsSavingPwd(true);
    try {
      await userService.changePassword({
        current_password: passwordData.current_password,
        new_password: passwordData.new_password,
      });
      setPasswordData({ current_password: '', new_password: '', confirm: '' });
      success('Contraseña actualizada correctamente');
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : 'Error al cambiar la contraseña');
    } finally {
      setIsSavingPwd(false);
    }
  };

  const cancelEdit = () => {
    setIsEditingProfile(false);
    setProfileData({ full_name: user.full_name, email: user.email });
    setProfileError('');
  };

  return (
    <DashboardLayout title="Mi Perfil">
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Información Personal */}
        <Card
          title="Información Personal"
          actions={
            !isEditingProfile ? (
              <Button variant="secondary" size="sm" onClick={() => setIsEditingProfile(true)} className="flex items-center gap-2">
                <Pencil className="w-3.5 h-3.5" />
                Editar
              </Button>
            ) : undefined
          }
        >
          {/* Avatar + resumen */}
          <div className="flex items-center gap-5 mb-6 pb-6 border-b border-stone-100 dark:border-stone-800">
            <UserAvatar initial={user.username[0].toUpperCase()} size="lg" />
            <div>
              <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
                {user.full_name || user.username}
              </h3>
              <p className="text-sm text-stone-400 dark:text-stone-500">@{user.username}</p>
              <div className="flex gap-2 mt-2 flex-wrap">
                {user.is_superuser && (
                  <span className="px-2 py-1 bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 text-xs font-medium rounded-full flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3" /> Superusuario
                  </span>
                )}
                {user.roles.map((r) => (
                  <span key={r.id} className="px-2 py-1 bg-violet-100 dark:bg-violet-900/40 text-violet-800 dark:text-violet-300 text-xs font-medium rounded-full">
                    {r.name}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {isEditingProfile ? (
            <div className="space-y-4">
              <ErrorAlert message={profileError} />
              <Input
                label="Nombre Completo"
                value={profileData.full_name ?? ''}
                onChange={(e) => setProfileData({ ...profileData, full_name: e.target.value })}
              />
              <Input
                label="Email *"
                type="email"
                value={profileData.email ?? ''}
                onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
              />
              <div className="flex gap-2 pt-1">
                <Button onClick={handleProfileSubmit} disabled={isSavingProfile} size="sm" className="flex items-center gap-1.5">
                  <Save className="w-3.5 h-3.5" />
                  {isSavingProfile ? 'Guardando...' : 'Guardar'}
                </Button>
                <Button variant="secondary" onClick={cancelEdit} size="sm" className="flex items-center gap-1.5">
                  <X className="w-3.5 h-3.5" />
                  Cancelar
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {[
                { label: 'Usuario',         value: user.username },
                { label: 'Nombre Completo', value: user.full_name || '—' },
                { label: 'Email',           value: user.email },
                { label: 'Estado',          value: null, isStatus: true },
                { label: 'Miembro desde',   value: user.created_at
                    ? new Date(user.created_at).toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' })
                    : '—' },
              ].map(({ label, value, isStatus }) => (
                <div key={label}>
                  <p className="text-xs font-medium text-stone-400 dark:text-stone-500 uppercase tracking-wider mb-1">
                    {label}
                  </p>
                  {isStatus ? (
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${
                      user.is_active
                        ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'
                        : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
                    }`}>
                      {user.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  ) : (
                    <p className="text-sm text-stone-800 dark:text-stone-200">{value}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Cambiar Contraseña */}
        <Card title="Cambiar Contraseña">
          <div className="flex items-center gap-2 mb-5 text-stone-400 dark:text-stone-500">
            <Lock className="w-4 h-4 shrink-0" />
            <span className="text-sm">Debes ingresar tu contraseña actual para confirmar el cambio.</span>
          </div>
          <div className="space-y-4 max-w-md">
            <Input
              label="Contraseña actual"
              type="password"
              value={passwordData.current_password}
              onChange={(e) => setPasswordData({ ...passwordData, current_password: e.target.value })}
              placeholder="Tu contraseña actual"
            />
            <Input
              label="Nueva contraseña"
              type="password"
              value={passwordData.new_password}
              onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
              placeholder="Mínimo 8 caracteres"
            />
            <Input
              label="Confirmar nueva contraseña"
              type="password"
              value={passwordData.confirm}
              onChange={(e) => setPasswordData({ ...passwordData, confirm: e.target.value })}
              placeholder="Repite la nueva contraseña"
            />
            <ErrorAlert message={passwordError} />
            <Button onClick={handlePasswordSubmit} disabled={isSavingPwd} size="sm" className="flex items-center gap-1.5">
              <Save className="w-3.5 h-3.5" />
              {isSavingPwd ? 'Cambiando...' : 'Cambiar Contraseña'}
            </Button>
          </div>
        </Card>

        {/* Roles y Permisos */}
        <Card title="Mis Roles y Permisos">
          <div className="space-y-6">
            <div>
              <h3 className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider mb-3">
                Roles Asignados
              </h3>
              <div className="flex flex-wrap gap-2">
                {user.roles.length > 0 ? (
                  user.roles.map((role) => (
                    <span key={role.id} className="px-3 py-1 bg-violet-100 dark:bg-violet-900/40 text-violet-800 dark:text-violet-300 text-sm rounded-md font-medium">
                      {role.name}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-stone-400 dark:text-stone-500">No tienes roles asignados</p>
                )}
              </div>
            </div>
            <div>
              <h3 className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider mb-3">
                Permisos ({user.roles.reduce((acc, role) => acc + role.permissions.length, 0)} totales)
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {user.roles.map((role) => (
                  <div key={role.id} className="border border-stone-200 dark:border-stone-700 rounded-md p-3">
                    <h4 className="text-xs font-semibold text-stone-600 dark:text-stone-400 mb-2 uppercase tracking-wide">
                      {role.name}
                    </h4>
                    <div className="space-y-1">
                      {role.permissions.map((perm) => (
                        <div key={perm.id} className="flex items-center gap-2 text-xs">
                          <span className="text-emerald-500 font-bold leading-none">✓</span>
                          <span className="text-stone-600 dark:text-stone-300 font-mono">{perm.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>

      </div>
    </DashboardLayout>
  );
}
