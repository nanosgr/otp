import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useToast } from '@/context/ToastContext';
import { useConfirm } from '@/lib/hooks/useConfirm';
import { ResourceDef, FieldDef, RESOURCE_BY_KEY } from '@/lib/resources';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import Table from '@/components/common/Table';
import Modal from '@/components/common/Modal';
import Input from '@/components/common/Input';
import Button from '@/components/common/Button';
import SearchBar from '@/components/common/SearchBar';
import ErrorAlert from '@/components/common/ErrorAlert';
import ModalFooter from '@/components/common/ModalFooter';
import ProtectedComponent from '@/components/common/ProtectedComponent';
import { TableColumn } from '@/types';

type Row = { id: number } & Record<string, unknown>;
type FormState = Record<string, unknown>;

interface Page {
  items: Row[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

const PAGE_SIZE = 15;

function display(field: FieldDef, value: unknown): React.ReactNode {
  if (value === null || value === undefined || value === '') return '—';
  if (field.type === 'checkbox') return value ? 'Sí' : 'No';
  if (field.type === 'json') return JSON.stringify(value);
  return String(value);
}

function toInput(field: FieldDef, value: unknown): unknown {
  if (field.type === 'json') return JSON.stringify(value ?? field.defaultValue ?? null, null, 2);
  if (value === undefined || value === null) return field.type === 'checkbox' ? false : '';
  return value;
}

function emptyForm(def: ResourceDef, preset: Record<string, string>): FormState {
  const form: FormState = {};
  for (const f of def.fields.filter((x) => !x.readOnly)) {
    const preset_ = preset[f.name];
    form[f.name] = preset_ !== undefined ? preset_ : toInput(f, f.defaultValue);
  }
  return form;
}

function buildPayload(def: ResourceDef, form: FormState): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const f of def.fields.filter((x) => !x.readOnly)) {
    const v = form[f.name];
    switch (f.type) {
      case 'checkbox':
        out[f.name] = Boolean(v);
        break;
      case 'number':
        out[f.name] = v === '' || v === null || v === undefined ? (f.required ? 0 : null) : Number(v);
        break;
      case 'json':
        out[f.name] = typeof v === 'string' && v.trim() !== '' ? JSON.parse(v) : null;
        break;
      case 'decimal':
        out[f.name] = v === '' || v === undefined ? (f.defaultValue !== undefined ? '0' : null) : v;
        break;
      default:
        out[f.name] = v === '' || v === undefined ? (f.required ? '' : null) : v;
    }
  }
  return out;
}

export default function ResourcePage({ resourceKey }: { resourceKey: string }) {
  const def = RESOURCE_BY_KEY[resourceKey];
  const { success, error: showError } = useToast();
  const { confirm, ConfirmationDialog } = useConfirm();
  const [params] = useSearchParams();

  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    for (const name of def.filters ?? []) {
      const value = params.get(name);
      if (value) f[name] = value;
    }
    return f;
  }, [def, params]);
  const filterKey = JSON.stringify(filters);

  const [data, setData] = useState<Page>({ items: [], total: 0, page: 1, size: PAGE_SIZE, pages: 1 });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editing, setEditing] = useState<Row | null>(null);
  const [form, setForm] = useState<FormState>({});
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => { setPage(1); }, [resourceKey, filterKey, search]);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const q = new URLSearchParams({ page: String(page), size: String(PAGE_SIZE), ...filters });
      if (search) q.set('search', search);
      setData(await apiClient.get<Page>(`/${def.path}/?${q.toString()}`));
    } catch (err) {
      showError(err instanceof Error ? err.message : `Error al cargar ${def.title.toLowerCase()}`);
    } finally {
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [def, page, search, filterKey, showError]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm(def, filters));
    setFormError('');
    setIsModalOpen(true);
  };

  const openEdit = (row: Row) => {
    setEditing(row);
    const f: FormState = {};
    for (const field of def.fields.filter((x) => !x.readOnly)) f[field.name] = toInput(field, row[field.name]);
    setForm(f);
    setFormError('');
    setIsModalOpen(true);
  };

  const handleSubmit = async () => {
    setFormError('');
    let payload: Record<string, unknown>;
    try {
      payload = buildPayload(def, form);
    } catch {
      setFormError('Hay un campo JSON con formato inválido');
      return;
    }
    setIsSubmitting(true);
    try {
      if (editing) {
        await apiClient.put(`/${def.path}/${editing.id}`, payload);
        success(`${def.singular} actualizado`);
      } else {
        await apiClient.post(`/${def.path}/`, payload);
        success(`${def.singular} creado`);
      }
      setIsModalOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Error al guardar');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (row: Row) => {
    const ok = await confirm({
      title: `Eliminar ${def.singular}`,
      message: `¿Está seguro de eliminar el registro #${row.id}? Esta acción no se puede deshacer.`,
      confirmText: 'Eliminar',
      cancelText: 'Cancelar',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await apiClient.delete(`/${def.path}/${row.id}`);
      success(`${def.singular} eliminado`);
      await load();
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Error al eliminar');
    }
  };

  const columns: TableColumn<Row>[] = [
    { key: 'id', label: 'ID' },
    ...def.fields
      .filter((f) => !f.hideInTable)
      .map((f) => ({ key: f.name, label: f.label, render: (row: Row) => display(f, row[f.name]) })),
    ...(def.related?.length || def.detail
      ? [{
          key: '_related',
          label: 'Ver',
          render: (row: Row) => (
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              {def.detail && (
                <Link className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline" to={def.detail.path(row.id)}>
                  {def.detail.label}
                </Link>
              )}
              {(def.related ?? []).map((r) => (
                <Link key={r.resource} className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  to={`/${RESOURCE_BY_KEY[r.resource].path}?${r.param}=${row.id}`}>
                  {r.label}
                </Link>
              ))}
            </div>
          ),
        }]
      : []),
  ];

  const renderField = (f: FieldDef) => {
    const value = form[f.name];
    const set = (v: unknown) => setForm((prev) => ({ ...prev, [f.name]: v }));
    if (f.type === 'checkbox') {
      return (
        <label key={f.name} className="flex items-center gap-2 text-sm text-stone-700 dark:text-stone-300">
          <input type="checkbox" checked={Boolean(value)} onChange={(e) => set(e.target.checked)} />
          {f.label}
        </label>
      );
    }
    if (f.type === 'select') {
      return (
        <div key={f.name}>
          <label className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">{f.label}</label>
          <select value={String(value ?? '')} onChange={(e) => set(e.target.value)}
            className="w-full px-3 py-2 text-sm rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100">
            {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      );
    }
    if (f.type === 'textarea' || f.type === 'json') {
      return (
        <div key={f.name}>
          <label className="block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1.5">{f.label}</label>
          <textarea rows={f.type === 'json' ? 5 : 3} value={String(value ?? '')} onChange={(e) => set(e.target.value)}
            className={`w-full px-3 py-2 text-sm rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100 ${f.type === 'json' ? 'font-mono' : ''}`} />
          {f.hint && <p className="mt-1 text-xs text-stone-400">{f.hint}</p>}
        </div>
      );
    }
    return (
      <div key={f.name}>
        <Input label={f.label + (f.required ? ' *' : '')}
          type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
          inputMode={f.type === 'decimal' ? 'decimal' : undefined}
          value={String(value ?? '')} onChange={(e) => set(e.target.value)} />
        {f.hint && <p className="mt-1 text-xs text-stone-400">{f.hint}</p>}
      </div>
    );
  };

  const filterInfo = Object.entries(filters).map(([k, v]) => `${k} = ${v}`).join(', ');

  return (
    <DashboardLayout title={def.title}>
      <Card
        title={`${def.title} (${data.total})`}
        actions={
          <ProtectedComponent permissions={[`${def.permission}:create`]}>
            <Button size="sm" onClick={openCreate}><Plus className="w-4 h-4 mr-1" />Nuevo</Button>
          </ProtectedComponent>
        }
      >
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {def.searchable && <SearchBar placeholder="Buscar..." onSearch={setSearch} />}
          {filterInfo && (
            <span className="text-xs text-stone-500 dark:text-stone-400">
              Filtrado por {filterInfo} · <Link className="underline" to={`/${def.path}`}>quitar filtro</Link>
            </span>
          )}
        </div>

        <Table<Row>
          data={data.items}
          columns={columns}
          isLoading={isLoading}
          actions={[
            { label: 'Editar', icon: <Pencil className="w-4 h-4" />, permission: `${def.permission}:update`, onClick: openEdit },
            { label: 'Eliminar', icon: <Trash2 className="w-4 h-4" />, permission: `${def.permission}:delete`, variant: 'danger', onClick: handleDelete },
          ]}
        />

        <div className="flex items-center justify-between mt-4 text-sm text-stone-500 dark:text-stone-400">
          <span>Página {data.page} de {data.pages}</span>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Anterior</Button>
            <Button size="sm" variant="secondary" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>Siguiente</Button>
          </div>
        </div>
      </Card>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editing ? `Editar ${def.singular}` : `Nuevo ${def.singular}`}
        size="lg"
        footer={<ModalFooter onCancel={() => setIsModalOpen(false)} onSubmit={handleSubmit} isSubmitting={isSubmitting} isEditing={!!editing} />}
      >
        <div className="space-y-4">
          {formError && <ErrorAlert message={formError} />}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {def.fields.filter((f) => !f.readOnly).map(renderField)}
          </div>
        </div>
      </Modal>
      <ConfirmationDialog />
    </DashboardLayout>
  );
}
