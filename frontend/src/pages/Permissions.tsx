import { useEffect, useState, useCallback } from 'react';
import { useToast } from '@/context/ToastContext';
import { useConfirm } from '@/lib/hooks/useConfirm';
import { usePagination } from '@/lib/hooks/usePagination';
import { useFilteredData } from '@/lib/hooks/useFilteredData';
import { permissionService } from '@/lib/api/services';
import { STATUS_FILTER_OPTIONS } from '@/lib/constants';
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
import { Permission, CreatePermissionDTO, UpdatePermissionDTO, TableColumn, TableAction } from '@/types';
import { KeyRound, Pencil, Trash2 } from 'lucide-react';

const PERMISSION_SEARCH_FIELDS = ['name', 'description', 'resource', 'action'];

export default function PermissionsPage() {
  const { success, error: showError } = useToast();
  const { confirm, ConfirmationDialog } = useConfirm();
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [availableResources, setAvailableResources] = useState<string[]>([]);
  const [availableActions, setAvailableActions] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPermission, setEditingPermission] = useState<Permission | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [resourceFilter, setResourceFilter] = useState('');
  const [formData, setFormData] = useState<CreatePermissionDTO>({
    name: '', description: '', resource: '', action: '', is_active: true,
  });
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [permsRes, resourcesRes, actionsRes] = await Promise.all([
        permissionService.getAll({ size: 500 }),
        permissionService.getAvailableResources(),
        permissionService.getAvailableActions(),
      ]);
      setPermissions(permsRes.items);
      setAvailableResources(resourcesRes.resources);
      setAvailableActions(actionsRes.actions);
    } catch {
      showError('Error al cargar los permisos');
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleCreate = () => {
    setEditingPermission(null);
    setFormData({ name: '', description: '', resource: '', action: '', is_active: true });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleEdit = (permission: Permission) => {
    setEditingPermission(permission);
    setFormData({
      name: permission.name,
      description: permission.description,
      resource: permission.resource,
      action: permission.action,
      is_active: permission.is_active,
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleDelete = async (permission: Permission) => {
    const confirmed = await confirm({
      title: 'Eliminar Permiso',
      message: `¿Está seguro de eliminar el permiso "${permission.name}"? Esta acción no se puede deshacer.`,
      confirmText: 'Eliminar',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await permissionService.delete(permission.id);
      success(`Permiso "${permission.name}" eliminado`);
      await loadData();
    } catch {
      showError('Error al eliminar el permiso');
    }
  };

  const handleResourceChange = (resource: string) => {
    setFormData((prev) => ({
      ...prev,
      resource,
      name: resource && prev.action ? `${resource}:${prev.action}` : prev.name,
    }));
  };

  const handleActionChange = (action: string) => {
    setFormData((prev) => ({
      ...prev,
      action,
      name: prev.resource && action ? `${prev.resource}:${action}` : prev.name,
    }));
  };

  const handleSubmit = async () => {
    setFormError('');
    setIsSubmitting(true);
    try {
      if (editingPermission) {
        const updateData: UpdatePermissionDTO = { name: formData.name, description: formData.description, is_active: formData.is_active };
        await permissionService.update(editingPermission.id, updateData);
        success('Permiso actualizado');
      } else {
        await permissionService.create({
          ...formData,
          name: formData.name || `${formData.resource}:${formData.action}`,
        });
        success('Permiso creado');
      }
      setIsModalOpen(false);
      await loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Error al guardar el permiso');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resourceExtraFilter = useCallback(
    (perm: Permission) => resourceFilter === '' || perm.resource === resourceFilter,
    [resourceFilter]
  );

  const filteredPermissions = useFilteredData({
    data: permissions,
    searchQuery,
    searchFields: PERMISSION_SEARCH_FIELDS,
    statusFilter,
    extraFilter: resourceFilter !== '' ? resourceExtraFilter : undefined,
  });

  const {
    currentPage, totalPages, currentData: paginatedPermissions,
    itemsPerPage, startIndex, endIndex,
    goToPage, nextPage, previousPage, goToFirstPage, goToLastPage, setItemsPerPage,
  } = usePagination({ data: filteredPermissions, itemsPerPage: 10 });

  const columns: TableColumn<Permission>[] = [
    {
      key: 'name',
      label: 'Nombre',
      render: (perm) => <span className="font-mono text-sm font-medium">{perm.name}</span>,
    },
    {
      key: 'resource',
      label: 'Recurso',
      render: (perm) => <span className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded font-medium">{perm.resource}</span>,
    },
    {
      key: 'action',
      label: 'Acción',
      render: (perm) => <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded font-medium">{perm.action}</span>,
    },
    { key: 'description', label: 'Descripción' },
    {
      key: 'is_active',
      label: 'Estado',
      render: (perm) => (
        <span className={`px-2 py-1 text-xs font-medium rounded ${perm.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {perm.is_active ? 'Activo' : 'Inactivo'}
        </span>
      ),
    },
  ];

  const actions: TableAction<Permission>[] = [
    { label: 'Editar', onClick: handleEdit, variant: 'secondary', permission: 'permissions:update', icon: <Pencil className="w-3 h-3" /> },
    { label: 'Eliminar', onClick: handleDelete, variant: 'danger', permission: 'permissions:delete', icon: <Trash2 className="w-3 h-3" /> },
  ];

  const resourceFilterOptions = [
    { value: '', label: 'Todos' },
    ...availableResources.map((r) => ({ value: r, label: r })),
  ];

  return (
    <DashboardLayout title="Gestión de Permisos">
      <Card
        title="Permisos del Sistema"
        actions={
          <ProtectedComponent permissions={['permissions:create']}>
            <Button onClick={handleCreate} className="flex items-center gap-2">
              <KeyRound className="w-4 h-4" />
              Nuevo Permiso
            </Button>
          </ProtectedComponent>
        }
      >
        <div className="mb-6 flex flex-col sm:flex-row gap-4 flex-wrap">
          <div className="flex-1 min-w-48">
            <SearchBar placeholder="Buscar por nombre, recurso o acción..." onSearch={setSearchQuery} />
          </div>
          <FilterSelect label="Recurso" value={resourceFilter} onChange={setResourceFilter} options={resourceFilterOptions} />
          <FilterSelect label="Estado" value={statusFilter} onChange={setStatusFilter} options={STATUS_FILTER_OPTIONS} />
        </div>

        <Table data={paginatedPermissions} columns={columns} actions={actions} isLoading={isLoading} emptyMessage="No se encontraron permisos" />

        {filteredPermissions.length > 0 && (
          <Pagination
            currentPage={currentPage} totalPages={totalPages}
            onPageChange={goToPage} onFirstPage={goToFirstPage} onLastPage={goToLastPage}
            onPreviousPage={previousPage} onNextPage={nextPage}
            startIndex={startIndex} endIndex={endIndex}
            totalItems={filteredPermissions.length} itemsPerPage={itemsPerPage}
            onItemsPerPageChange={setItemsPerPage}
          />
        )}
      </Card>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingPermission ? 'Editar Permiso' : 'Crear Permiso'}
        footer={
          <ModalFooter
            onCancel={() => setIsModalOpen(false)}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
            isEditing={!!editingPermission}
          />
        }
      >
        <div className="space-y-4">
          <ErrorAlert message={formError} />
          {editingPermission ? (
            <div className="flex gap-2 p-3 bg-stone-50 dark:bg-stone-800 rounded-md">
              <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300 text-xs rounded">{editingPermission.resource}</span>
              <span className="px-2 py-1 bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-300 text-xs rounded">{editingPermission.action}</span>
              <span className="text-xs text-stone-400 dark:text-stone-500 self-center">— inmutables</span>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">Recurso *</label>
                <select
                  value={formData.resource}
                  onChange={(e) => handleResourceChange(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-colors"
                >
                  <option value="" className="bg-white dark:bg-stone-900">Seleccionar recurso...</option>
                  {availableResources.map((r) => <option key={r} value={r} className="bg-white dark:bg-stone-900">{r}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">Acción *</label>
                <select
                  value={formData.action}
                  onChange={(e) => handleActionChange(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-colors"
                >
                  <option value="" className="bg-white dark:bg-stone-900">Seleccionar acción...</option>
                  {availableActions.map((a) => <option key={a} value={a} className="bg-white dark:bg-stone-900">{a}</option>)}
                </select>
              </div>
            </>
          )}
          <Input
            label="Nombre"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Se auto-genera como recurso:acción"
          />
          <Input
            label="Descripción"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Descripción del permiso"
          />
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              className="rounded accent-blue-600"
            />
            <span className="text-sm font-medium text-stone-700 dark:text-stone-300">Permiso Activo</span>
          </label>
        </div>
      </Modal>

      <ConfirmationDialog />
    </DashboardLayout>
  );
}
