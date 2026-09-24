import { useEffect, useState, useCallback } from 'react';
import { useToast } from '@/context/ToastContext';
import { useConfirm } from '@/lib/hooks/useConfirm';
import { usePagination } from '@/lib/hooks/usePagination';
import { useFilteredData } from '@/lib/hooks/useFilteredData';
import { roleService, permissionService } from '@/lib/api/services';
import { STATUS_FILTER_OPTIONS, SCOPE_OPTIONS, EFFECT_OPTIONS } from '@/lib/constants';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import Table from '@/components/common/Table';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import ProtectedComponent from '@/components/common/ProtectedComponent';
import SearchBar from '@/components/common/SearchBar';
import FilterSelect from '@/components/common/FilterSelect';
import Pagination from '@/components/common/Pagination';
import ErrorAlert from '@/components/common/ErrorAlert';
import ModalFooter from '@/components/common/ModalFooter';
import EffectivePermissionsModal from '@/components/roles/EffectivePermissionsModal';
import {
  Role, Permission, CreateRoleDTO, UpdateRoleDTO, TableColumn, TableAction,
  PermissionRule, RuleEffect, RuleScope,
} from '@/types';
import { ShieldPlus, Pencil, Trash2, ListChecks } from 'lucide-react';

const ROLE_SEARCH_FIELDS = ['name', 'description'];

const selectClass =
  'px-2 py-1 text-xs rounded border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-700 dark:text-stone-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500';

function defaultRule(permissionId: number): PermissionRule {
  return { permission_id: permissionId, effect: 'allow', assertion: null, scope: 'all', scope_dimension: null };
}

export default function RolesPage() {
  const { success, error: showError } = useToast();
  const { confirm, ConfirmationDialog } = useConfirm();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [effectiveRole, setEffectiveRole] = useState<Role | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [formData, setFormData] = useState<Omit<CreateRoleDTO, 'permission_ids'>>({
    name: '',
    description: '',
    is_active: true,
  });
  // reglas por permiso: sólo las claves presentes están asignadas al rol
  const [rules, setRules] = useState<Record<number, PermissionRule>>({});
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [rolesRes, permsRes] = await Promise.all([
        roleService.getAll({ size: 500 }),
        permissionService.getAll({ size: 500, is_active: true }),
      ]);
      setRoles(rolesRes.items);
      setPermissions(permsRes.items);
    } catch {
      showError('Error al cargar los datos');
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCreate = () => {
    setEditingRole(null);
    setFormData({ name: '', description: '', is_active: true });
    setRules({});
    setFormError('');
    setIsModalOpen(true);
  };

  const handleEdit = async (role: Role) => {
    setEditingRole(role);
    setFormData({ name: role.name, description: role.description, is_active: role.is_active });
    setFormError('');
    setRules({});
    setIsModalOpen(true);
    try {
      const roleRules = await roleService.getPermissionRules(role.id);
      const map: Record<number, PermissionRule> = {};
      for (const r of roleRules) {
        map[r.permission_id] = {
          permission_id: r.permission_id,
          effect: (r.effect as RuleEffect) ?? 'allow',
          assertion: r.assertion ?? null,
          scope: (r.scope as RuleScope) ?? 'all',
          scope_dimension: r.scope_dimension ?? null,
        };
      }
      setRules(map);
    } catch {
      showError('No se pudieron cargar las reglas del rol');
    }
  };

  const handleDelete = async (role: Role) => {
    const confirmed = await confirm({
      title: 'Eliminar Rol',
      message: `¿Está seguro de eliminar el rol "${role.name}"? Esta acción no se puede deshacer.`,
      confirmText: 'Eliminar',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await roleService.delete(role.id);
      success(`Rol "${role.name}" eliminado`);
      await loadData();
    } catch {
      showError('Error al eliminar el rol');
    }
  };

  const togglePermission = (permId: number, checked: boolean) => {
    setRules((prev) => {
      const next = { ...prev };
      if (checked) next[permId] = defaultRule(permId);
      else delete next[permId];
      return next;
    });
  };

  const patchRule = (permId: number, patch: Partial<PermissionRule>) => {
    setRules((prev) => {
      const current = prev[permId];
      if (!current) return prev;
      const merged = { ...current, ...patch };
      if (merged.scope !== 'attribute') merged.scope_dimension = null;
      return { ...prev, [permId]: merged };
    });
  };

  const handleSubmit = async () => {
    setFormError('');
    const ruleList = Object.values(rules);
    const missingDimension = ruleList.find((r) => r.scope === 'attribute' && !r.scope_dimension?.trim());
    if (missingDimension) {
      const perm = permissions.find((p) => p.id === missingDimension.permission_id);
      setFormError(`Indicá la dimensión para el alcance «por atributo» de "${perm?.name ?? 'un permiso'}".`);
      return;
    }
    setIsSubmitting(true);
    try {
      const payload = ruleList.map((r) => ({
        ...r,
        scope_dimension: r.scope === 'attribute' ? r.scope_dimension?.trim() || null : null,
      }));
      if (editingRole) {
        const updateData: UpdateRoleDTO = { name: formData.name, description: formData.description, is_active: formData.is_active };
        await roleService.update(editingRole.id, updateData);
        await roleService.assignPermissionRules(editingRole.id, payload);
        success('Rol actualizado');
      } else {
        const newRole = await roleService.create(formData);
        if (payload.length > 0) {
          await roleService.assignPermissionRules(newRole.id, payload);
        }
        success('Rol creado');
      }
      setIsModalOpen(false);
      await loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Error al guardar el rol');
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredRoles = useFilteredData({
    data: roles,
    searchQuery,
    searchFields: ROLE_SEARCH_FIELDS,
    statusFilter,
  });

  const {
    currentPage, totalPages, currentData: paginatedRoles,
    itemsPerPage, startIndex, endIndex,
    goToPage, nextPage, previousPage, goToFirstPage, goToLastPage, setItemsPerPage,
  } = usePagination({ data: filteredRoles, itemsPerPage: 10 });

  const roleNames = roles.reduce((acc, r) => { acc[r.id] = r.name; return acc; }, {} as Record<number, string>);

  const groupedPermissions = permissions.reduce((acc, perm) => {
    if (!acc[perm.resource]) acc[perm.resource] = [];
    acc[perm.resource].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  const selectedCount = Object.keys(rules).length;
  const scopedCount = Object.values(rules).filter((r) => r.scope !== 'all' || r.effect === 'deny').length;

  const columns: TableColumn<Role>[] = [
    {
      key: 'name',
      label: 'Nombre',
      render: (role) => <span className="font-medium text-stone-800 dark:text-stone-200">{role.name}</span>,
    },
    { key: 'description', label: 'Descripción' },
    {
      key: 'permissions',
      label: 'Permisos',
      render: (role) => (
        <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded-full">
          {(role.permissions ?? []).length} permisos
        </span>
      ),
    },
    {
      key: 'is_active',
      label: 'Estado',
      render: (role) => (
        <span className={`px-2 py-1 text-xs font-medium rounded ${role.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {role.is_active ? 'Activo' : 'Inactivo'}
        </span>
      ),
    },
  ];

  const actions: TableAction<Role>[] = [
    { label: 'Permisos efectivos', onClick: (r) => setEffectiveRole(r), permission: 'roles:read', icon: <ListChecks className="w-3 h-3" /> },
    { label: 'Editar', onClick: handleEdit, variant: 'secondary', permission: 'roles:update', icon: <Pencil className="w-3 h-3" /> },
    { label: 'Eliminar', onClick: handleDelete, variant: 'danger', permission: 'roles:delete', icon: <Trash2 className="w-3 h-3" /> },
  ];

  return (
    <DashboardLayout title="Gestión de Roles">
      <Card
        title="Roles del Sistema"
        actions={
          <ProtectedComponent permissions={['roles:create']}>
            <Button onClick={handleCreate} className="flex items-center gap-2">
              <ShieldPlus className="w-4 h-4" />
              Nuevo Rol
            </Button>
          </ProtectedComponent>
        }
      >
        <div className="mb-6 flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <SearchBar placeholder="Buscar por nombre o descripción..." onSearch={setSearchQuery} />
          </div>
          <FilterSelect label="Estado" value={statusFilter} onChange={setStatusFilter} options={STATUS_FILTER_OPTIONS} />
        </div>

        <Table data={paginatedRoles} columns={columns} actions={actions} isLoading={isLoading} emptyMessage="No se encontraron roles" />

        {filteredRoles.length > 0 && (
          <Pagination
            currentPage={currentPage} totalPages={totalPages}
            onPageChange={goToPage} onFirstPage={goToFirstPage} onLastPage={goToLastPage}
            onPreviousPage={previousPage} onNextPage={nextPage}
            startIndex={startIndex} endIndex={endIndex}
            totalItems={filteredRoles.length} itemsPerPage={itemsPerPage}
            onItemsPerPageChange={setItemsPerPage}
          />
        )}
      </Card>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingRole ? 'Editar Rol' : 'Crear Rol'}
        size="xl"
        footer={
          <ModalFooter
            onCancel={() => setIsModalOpen(false)}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
            isEditing={!!editingRole}
          />
        }
      >
        <div className="space-y-4">
          <ErrorAlert message={formError} />
          <Input
            label="Nombre *"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />
          <div>
            <label className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">Descripción</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 text-sm rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100 placeholder:text-stone-400 dark:placeholder:text-stone-600 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-colors"
              rows={2}
            />
          </div>

          <div>
            <div className="flex items-baseline justify-between mb-1.5">
              <label className="block text-xs font-medium text-stone-600 dark:text-stone-400">
                Permisos y alcance ({selectedCount} asignados{scopedCount > 0 ? `, ${scopedCount} con regla` : ''})
              </label>
            </div>
            <p className="text-xs text-stone-400 dark:text-stone-500 mb-2">
              Por cada permiso elegí si <strong>permite o deniega</strong>, y sobre qué filas aplica:
              todas, sólo las propias del usuario, o filtradas por una dimensión (ej.{' '}
              <code className="font-mono">warehouse</code>) definida en los alcances del usuario.
            </p>
            <div className="border border-stone-200 dark:border-stone-700 rounded-md p-3 max-h-96 overflow-y-auto bg-white dark:bg-stone-900 space-y-4">
              {Object.entries(groupedPermissions).map(([resource, perms]) => (
                <div key={resource}>
                  <h4 className="font-semibold text-stone-500 dark:text-stone-400 mb-2 uppercase text-xs tracking-wide">{resource}</h4>
                  <div className="space-y-1.5 ml-1">
                    {perms.map((perm) => {
                      const rule = rules[perm.id];
                      return (
                        <div key={perm.id} className="flex flex-wrap items-center gap-2 py-1">
                          <label className="flex items-center gap-2 cursor-pointer min-w-40">
                            <input
                              type="checkbox"
                              checked={!!rule}
                              onChange={(e) => togglePermission(perm.id, e.target.checked)}
                              className="rounded accent-blue-600"
                            />
                            <span className="text-sm text-stone-700 dark:text-stone-300 font-mono">{perm.action}</span>
                            {perm.resource === '*' && (
                              <span className="text-[10px] px-1 rounded bg-stone-100 dark:bg-stone-800 text-stone-500">wildcard</span>
                            )}
                          </label>

                          {rule && (
                            <div className="flex flex-wrap items-center gap-1.5">
                              <select
                                value={rule.effect}
                                onChange={(e) => patchRule(perm.id, { effect: e.target.value as RuleEffect })}
                                className={`${selectClass} ${rule.effect === 'deny' ? 'text-red-600 dark:text-red-400 border-red-300 dark:border-red-800' : ''}`}
                              >
                                {EFFECT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                              </select>

                              {rule.effect === 'allow' && (
                                <>
                                  <select
                                    value={rule.scope}
                                    onChange={(e) => patchRule(perm.id, { scope: e.target.value as RuleScope })}
                                    className={selectClass}
                                    title="Alcance de datos"
                                  >
                                    {SCOPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                                  </select>
                                  {rule.scope === 'attribute' && (
                                    <input
                                      type="text"
                                      value={rule.scope_dimension ?? ''}
                                      placeholder="dimensión (ej. warehouse)"
                                      onChange={(e) => patchRule(perm.id, { scope_dimension: e.target.value })}
                                      className={`${selectClass} w-44`}
                                    />
                                  )}
                                </>
                              )}

                              {rule.assertion && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400" title="assertion (editable por API)">
                                  {rule.assertion}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              className="rounded accent-blue-600"
            />
            <span className="text-sm font-medium text-stone-700 dark:text-stone-300">Rol Activo</span>
          </label>
        </div>
      </Modal>

      <EffectivePermissionsModal role={effectiveRole} roleNames={roleNames} onClose={() => setEffectiveRole(null)} />

      <ConfirmationDialog />
    </DashboardLayout>
  );
}
