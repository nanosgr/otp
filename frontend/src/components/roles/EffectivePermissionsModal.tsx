import { useCallback, useEffect, useState } from 'react';
import { Check, Ban, HelpCircle, Filter } from 'lucide-react';
import Modal from '@/components/common/Modal';
import Button from '@/components/common/Button';
import { roleService } from '@/lib/api/services';
import { useToast } from '@/context/ToastContext';
import { EffectivePermissions, Role, RuleScope } from '@/types';
import { SCOPE_LABELS } from '@/lib/constants';

interface Props {
  role: Role | null;
  roleNames: Record<number, string>;
  onClose: () => void;
}

function PatternPill({ children, className }: { children: React.ReactNode; className: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono ${className}`}>{children}</span>
  );
}

/**
 * Muestra los permisos ya resueltos sobre la jerarquía del rol:
 * allow / deny / condicionales (assertion) / acotados por alcance (scope).
 */
export default function EffectivePermissionsModal({ role, roleNames, onClose }: Props) {
  const { error: showError } = useToast();
  const [data, setData] = useState<EffectivePermissions | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const load = useCallback(async (roleId: number) => {
    setIsLoading(true);
    try {
      setData(await roleService.getEffectivePermissions(roleId));
    } catch {
      showError('No se pudieron cargar los permisos efectivos');
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    if (role) load(role.id);
    else setData(null);
  }, [role, load]);

  if (!role) return null;

  const section = (
    title: string,
    icon: React.ReactNode,
    items: React.ReactNode[],
    empty: string,
  ) => (
    <div>
      <h4 className="flex items-center gap-1.5 text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wide mb-2">
        {icon}
        {title}
      </h4>
      {items.length === 0 ? (
        <p className="text-xs text-stone-400 dark:text-stone-500">{empty}</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">{items}</div>
      )}
    </div>
  );

  return (
    <Modal
      isOpen={!!role}
      onClose={onClose}
      title={`Permisos efectivos — ${role.name}`}
      size="lg"
      footer={<Button variant="secondary" onClick={onClose}>Cerrar</Button>}
    >
      {isLoading || !data ? (
        <p className="text-sm text-stone-400 py-6 text-center">Cargando...</p>
      ) : (
        <div className="space-y-5">
          <div className="text-xs text-stone-500 dark:text-stone-400">
            Resuelto sobre{' '}
            {data.contributing_role_ids.length === 1 ? 'el rol' : 'los roles'}:{' '}
            {data.contributing_role_ids.map((id) => roleNames[id] ?? `#${id}`).join(', ')}
          </div>

          {section(
            'Permitidos',
            <Check className="w-3.5 h-3.5 text-emerald-600" />,
            data.allow.map((p) => (
              <PatternPill key={p} className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                {p}
              </PatternPill>
            )),
            'Ninguno',
          )}

          {section(
            'Denegados (ganan siempre)',
            <Ban className="w-3.5 h-3.5 text-red-600" />,
            data.deny.map((p) => (
              <PatternPill key={p} className="bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400">
                {p}
              </PatternPill>
            )),
            'Ninguno',
          )}

          {section(
            'Condicionales (assertion)',
            <HelpCircle className="w-3.5 h-3.5 text-amber-600" />,
            data.conditional.map((c) => (
              <PatternPill key={`${c.pattern}:${c.assertion}`} className="bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                {c.pattern} · {c.assertion}
              </PatternPill>
            )),
            'Ninguno',
          )}

          {section(
            'Acotados por alcance',
            <Filter className="w-3.5 h-3.5 text-blue-600" />,
            data.scoped.map((s) => (
              <PatternPill key={`${s.pattern}:${s.scope}:${s.dimension ?? ''}`} className="bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400">
                {s.pattern} · {SCOPE_LABELS[s.scope as RuleScope] ?? s.scope}
                {s.dimension ? ` (${s.dimension})` : ''}
              </PatternPill>
            )),
            'Ninguno',
          )}
        </div>
      )}
    </Modal>
  );
}
