import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import ProtectedComponent from '@/components/common/ProtectedComponent';
import UserAvatar from '@/components/common/UserAvatar';
import {
  LayoutDashboard,
  User,
  Users,
  Shield,
  Key,
  ClipboardList,
  LogOut,
  X,
  type LucideIcon,
} from 'lucide-react';
import { NAV_RESOURCE_KEYS, RESOURCE_BY_KEY } from '@/lib/resources';

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  permissions?: string[];
}

const navItems: NavItem[] = [
  { label: 'Dashboard',  href: '/dashboard',   icon: LayoutDashboard, permissions: ['dashboard:read'] },
  { label: 'Mi Perfil',  href: '/profile',     icon: User },
  ...NAV_RESOURCE_KEYS.map((k) => {
    const r = RESOURCE_BY_KEY[k];
    return { label: r.title, href: `/${r.path}`, icon: r.icon, permissions: [`${r.permission}:read`] };
  }),
  { label: 'Usuarios',   href: '/users',       icon: Users,  permissions: ['users:read'] },
  { label: 'Roles',      href: '/roles',       icon: Shield, permissions: ['roles:read'] },
  { label: 'Permisos',   href: '/permissions', icon: Key,    permissions: ['permissions:read'] },
  { label: 'Auditoría',  href: '/audit',       icon: ClipboardList, permissions: ['audit:read'] },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { pathname } = useLocation();
  const { user, logout } = useAuth();

  const initial = user?.username?.[0]?.toUpperCase() ?? '?';

  return (
    <>
      {/* Overlay mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-20 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-30
          w-64 flex flex-col
          bg-white dark:bg-stone-900
          border-r border-stone-200 dark:border-stone-800
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-14 px-5 border-b border-stone-200 dark:border-stone-800 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-stone-900 dark:bg-white flex items-center justify-center">
              <Shield className="w-4 h-4 text-white dark:text-stone-900" />
            </div>
            <span className="text-sm font-semibold text-stone-800 dark:text-stone-100 tracking-tight">
              online-otp
            </span>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* User info */}
        <div className="px-4 py-3 border-b border-stone-200 dark:border-stone-800 shrink-0">
          <div className="flex items-center gap-3">
            <UserAvatar initial={initial} size="sm" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-stone-800 dark:text-stone-100 truncate leading-tight">
                {user?.full_name || user?.username}
              </p>
              <p className="text-xs text-stone-400 dark:text-stone-500 truncate">
                {user?.roles?.[0]?.name ?? 'Usuario'}
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <ProtectedComponent key={item.href} permissions={item.permissions}>
                <Link
                  to={item.href}
                  onClick={() => { if (window.innerWidth < 1024) onClose(); }}
                  className={`
                    flex items-center gap-3 px-3 py-2 rounded-md text-sm
                    transition-colors duration-150
                    ${isActive
                      ? 'bg-stone-100 dark:bg-stone-800 text-stone-900 dark:text-stone-100 font-medium'
                      : 'text-stone-500 dark:text-stone-400 hover:bg-stone-50 dark:hover:bg-stone-800/60 hover:text-stone-800 dark:hover:text-stone-200'
                    }
                  `}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-stone-700 dark:text-stone-200' : ''}`} />
                  <span>{item.label}</span>
                </Link>
              </ProtectedComponent>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="px-3 py-3 border-t border-stone-200 dark:border-stone-800 shrink-0">
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm text-stone-500 dark:text-stone-400 hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-600 dark:hover:text-red-400 transition-colors duration-150"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            <span>Cerrar sesión</span>
          </button>
        </div>
      </aside>
    </>
  );
}
