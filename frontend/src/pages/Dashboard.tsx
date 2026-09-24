import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { userService, roleService, permissionService } from '@/lib/api/services';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import { User } from '@/types';
import UserAvatar from '@/components/common/UserAvatar';
import { Users, ShieldCheck, KeyRound, Star } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  sub: string;
  icon: React.ReactNode;
  iconBg: string;
}

function StatCard({ label, value, sub, icon, iconBg }: StatCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-stone-500 dark:text-stone-400">{label}</p>
          <p className="text-2xl font-semibold text-stone-800 dark:text-stone-100 mt-1 tabular-nums">
            {value}
          </p>
          <p className="text-xs text-stone-400 dark:text-stone-500 mt-1">{sub}</p>
        </div>
        <div className={`w-9 h-9 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
          {icon}
        </div>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState({ totalUsers: 0, totalRoles: 0, totalPermissions: 0, activeUsers: 0 });
  const [recentUsers, setRecentUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [usersRes, rolesRes, permsRes, recentRes, activeRes] = await Promise.all([
          userService.getAll({ page: 1, size: 1 }).catch(() => null),
          roleService.getAll({ page: 1, size: 1 }).catch(() => null),
          permissionService.getAll({ page: 1, size: 1 }).catch(() => null),
          userService.getAll({ page: 1, size: 5 }).catch(() => null),
          userService.getAll({ page: 1, size: 1, is_active: true }).catch(() => null),
        ]);

        setStats({
          totalUsers: usersRes?.total ?? 0,
          totalRoles: rolesRes?.total ?? 0,
          totalPermissions: permsRes?.total ?? 0,
          activeUsers: activeRes?.total ?? 0,
        });
        setRecentUsers(recentRes?.items ?? []);
      } catch { /* sin permisos suficientes */ }
      finally { setIsLoading(false); }
    };
    load();
  }, []);

  return (
    <DashboardLayout title="Panel de Control">
      <div className="space-y-6 max-w-6xl">
        {/* Welcome banner */}
        <div className="rounded-lg bg-stone-100 dark:bg-stone-800 border border-stone-200 dark:border-stone-700 px-5 py-4">
          <p className="text-xs font-medium text-stone-400 dark:text-stone-500 uppercase tracking-wider">Bienvenido</p>
          <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mt-0.5">{user?.full_name}</h2>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
            {user?.roles?.[0]?.name ?? 'Usuario'} · Oficina Técnico Previsional
          </p>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard
            label="Usuarios"
            value={isLoading ? '—' : stats.totalUsers}
            sub={`${stats.activeUsers} activos`}
            icon={<Users className="w-4 h-4 text-blue-600" />}
            iconBg="bg-blue-50 dark:bg-blue-950/50"
          />
          <StatCard
            label="Roles"
            value={isLoading ? '—' : stats.totalRoles}
            sub="Roles del sistema"
            icon={<ShieldCheck className="w-4 h-4 text-violet-600" />}
            iconBg="bg-violet-50 dark:bg-violet-950/50"
          />
          <StatCard
            label="Permisos"
            value={isLoading ? '—' : stats.totalPermissions}
            sub="Configurados"
            icon={<KeyRound className="w-4 h-4 text-emerald-600" />}
            iconBg="bg-emerald-50 dark:bg-emerald-950/50"
          />
          <StatCard
            label="Mi Rol"
            value={user?.roles?.[0]?.name ?? 'N/A'}
            sub={user?.is_superuser ? 'Acceso total' : 'Acceso limitado'}
            icon={<Star className="w-4 h-4 text-amber-500" />}
            iconBg="bg-amber-50 dark:bg-amber-950/50"
          />
        </div>

        {/* Content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card title="Usuarios recientes">
            {isLoading ? (
              <div className="text-sm text-stone-400 py-4 text-center">Cargando...</div>
            ) : recentUsers.length > 0 ? (
              <div className="space-y-2">
                {recentUsers.map((u) => (
                  <div
                    key={u.id}
                    className="flex items-center justify-between gap-3 py-2 border-b border-stone-50 dark:border-stone-800 last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <UserAvatar initial={u.username[0].toUpperCase()} size="sm" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-stone-700 dark:text-stone-200 truncate">
                          {u.full_name}
                        </p>
                        <p className="text-xs text-stone-400 truncate">{u.email}</p>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 px-2 py-0.5 text-xs font-medium rounded-full ${
                        u.is_active
                          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400'
                          : 'bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-400'
                      }`}
                    >
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-stone-400 py-4 text-center">No hay usuarios registrados</p>
            )}
          </Card>

          <Card title="Mis permisos">
            {user?.roles && user.roles.length > 0 ? (
              <div className="space-y-3">
                {user.roles.map((role) => (
                  <div key={role.id}>
                    <p className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider mb-2">
                      {role.name}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {role.permissions.slice(0, 8).map((perm) => (
                        <span
                          key={perm.id}
                          className="px-2 py-0.5 bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 text-xs rounded font-mono"
                        >
                          {perm.name}
                        </span>
                      ))}
                      {role.permissions.length > 8 && (
                        <span className="px-2 py-0.5 bg-stone-100 dark:bg-stone-800 text-stone-400 text-xs rounded">
                          +{role.permissions.length - 8}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-stone-400 py-4 text-center">No tienes roles asignados</p>
            )}
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
