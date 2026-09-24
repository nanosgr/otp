import { useEffect, useState, useCallback } from 'react';
import { useToast } from '@/context/ToastContext';
import { auditService } from '@/lib/api/services';
import DashboardLayout from '@/components/layout/DashboardLayout';
import Card from '@/components/common/Card';
import Table from '@/components/common/Table';
import Pagination from '@/components/common/Pagination';
import FilterSelect from '@/components/common/FilterSelect';
import { AuditLog, TableColumn, GetAuditLogsParams } from '@/types';
import { ClipboardList, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';

const ACTION_OPTIONS = [
  { value: 'all', label: 'Todas las acciones' },
  { value: 'login', label: 'Login' },
  { value: 'logout', label: 'Logout' },
  { value: 'create', label: 'Crear' },
  { value: 'update', label: 'Actualizar' },
  { value: 'delete', label: 'Eliminar' },
  { value: 'assign_roles', label: 'Asignar roles' },
  { value: 'assign_permissions', label: 'Asignar permisos' },
  { value: 'assign_parents', label: 'Asignar roles padre' },
  { value: 'set_scopes', label: 'Definir alcances' },
  { value: 'password_change', label: 'Cambio de contraseña' },
];

const RESOURCE_OPTIONS = [
  { value: 'all', label: 'Todos los recursos' },
  { value: 'auth', label: 'Autenticación' },
  { value: 'user', label: 'Usuario' },
  { value: 'role', label: 'Rol' },
  { value: 'permission', label: 'Permiso' },
  { value: 'order', label: 'Pedido' },
];

const STATUS_OPTIONS = [
  { value: 'all', label: 'Todos los estados' },
  { value: 'success', label: 'Exitoso' },
  { value: 'failure', label: 'Fallido' },
];

function StatusBadge({ status }: { status: string }) {
  if (status === 'success') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
        <CheckCircle className="w-3 h-3" />
        Exitoso
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400">
      <XCircle className="w-3 h-3" />
      Fallido
    </span>
  );
}

function DiffViewer({ before, after }: { before: string | null; after: string | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!before && !after) return <span className="text-stone-400 text-xs">—</span>;

  const parse = (s: string | null) => {
    try { return s ? JSON.parse(s) : null; } catch { return s; }
  };

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1 text-xs text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 transition-colors"
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        Ver diff
      </button>
      {expanded && (
        <div className="mt-1 space-y-1">
          {before && (
            <pre className="text-xs bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 p-2 rounded overflow-auto max-w-xs">
              {JSON.stringify(parse(before), null, 2)}
            </pre>
          )}
          {after && (
            <pre className="text-xs bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 p-2 rounded overflow-auto max-w-xs">
              {JSON.stringify(parse(after), null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function AuditPage() {
  const { error: showError } = useToast();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [isLoading, setIsLoading] = useState(true);

  const [actionFilter, setActionFilter] = useState('all');
  const [resourceFilter, setResourceFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  const loadLogs = useCallback(async (currentPage: number, size: number) => {
    setIsLoading(true);
    try {
      const params: GetAuditLogsParams = {
        page: currentPage,
        size,
        ...(actionFilter !== 'all' && { action: actionFilter }),
        ...(resourceFilter !== 'all' && { resource: resourceFilter }),
        ...(statusFilter !== 'all' && { status: statusFilter }),
        ...(fromDate && { from_date: new Date(fromDate).toISOString() }),
        ...(toDate && { to_date: new Date(toDate).toISOString() }),
      };
      const res = await auditService.getLogs(params);
      setLogs(res.items);
      setTotal(res.total);
      setPages(res.pages || 1);
    } catch {
      showError('Error al cargar los logs de auditoría');
    } finally {
      setIsLoading(false);
    }
  }, [actionFilter, resourceFilter, statusFilter, fromDate, toDate, showError]);

  useEffect(() => {
    setPage(1);
  }, [actionFilter, resourceFilter, statusFilter, fromDate, toDate, pageSize]);

  useEffect(() => {
    loadLogs(page, pageSize);
  }, [loadLogs, page, pageSize]);

  const formatDate = (ts: string | null) => {
    if (!ts) return '—';
    return new Date(ts).toLocaleString('es-ES', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  };

  const startIndex = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  const columns: TableColumn<AuditLog>[] = [
    {
      key: 'timestamp',
      label: 'Fecha',
      render: (log) => (
        <span className="text-xs text-stone-500 dark:text-stone-400 whitespace-nowrap">
          {formatDate(log.timestamp)}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Estado',
      render: (log) => <StatusBadge status={log.status} />,
    },
    {
      key: 'username',
      label: 'Actor',
      render: (log) => (
        <span className="font-medium text-sm text-stone-700 dark:text-stone-200">
          {log.username ?? '—'}
        </span>
      ),
    },
    {
      key: 'action',
      label: 'Acción',
      render: (log) => (
        <span className="text-xs font-mono bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 px-1.5 py-0.5 rounded">
          {log.action}
        </span>
      ),
    },
    {
      key: 'resource',
      label: 'Recurso',
      render: (log) => (
        <span className="text-sm text-stone-600 dark:text-stone-300">
          {log.resource}{log.resource_id ? ` #${log.resource_id}` : ''}
        </span>
      ),
    },
    {
      key: 'before_data',
      label: 'Cambios',
      render: (log) => <DiffViewer before={log.before_data} after={log.after_data} />,
    },
    {
      key: 'ip_address',
      label: 'IP',
      render: (log) => (
        <span className="text-xs text-stone-400 dark:text-stone-500 font-mono">
          {log.ip_address ?? '—'}
        </span>
      ),
    },
    {
      key: 'request_id',
      label: 'Request ID',
      render: (log) => (
        <span
          className="text-xs text-stone-400 dark:text-stone-500 font-mono truncate max-w-[100px] block"
          title={log.request_id ?? ''}
        >
          {log.request_id ? log.request_id.slice(0, 8) + '…' : '—'}
        </span>
      ),
    },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-stone-900 dark:bg-stone-100 flex items-center justify-center">
            <ClipboardList className="w-4 h-4 text-white dark:text-stone-900" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-stone-800 dark:text-stone-100">Auditoría</h1>
            <p className="text-xs text-stone-500 dark:text-stone-400">{total} registros</p>
          </div>
        </div>

        {/* Filtros */}
        <Card>
          <div className="flex flex-wrap gap-3 items-end">
            <FilterSelect
              value={actionFilter}
              onChange={setActionFilter}
              options={ACTION_OPTIONS as { value: string; label: string }[]}
              label="Acción"
            />
            <FilterSelect
              value={resourceFilter}
              onChange={setResourceFilter}
              options={RESOURCE_OPTIONS as { value: string; label: string }[]}
              label="Recurso"
            />
            <FilterSelect
              value={statusFilter}
              onChange={setStatusFilter}
              options={STATUS_OPTIONS as { value: string; label: string }[]}
              label="Estado"
            />
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-stone-500 dark:text-stone-400">Desde</label>
              <input
                type="datetime-local"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="text-sm px-3 py-1.5 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 text-stone-700 dark:text-stone-200 focus:outline-none focus:ring-2 focus:ring-stone-400"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-stone-500 dark:text-stone-400">Hasta</label>
              <input
                type="datetime-local"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="text-sm px-3 py-1.5 rounded-md border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 text-stone-700 dark:text-stone-200 focus:outline-none focus:ring-2 focus:ring-stone-400"
              />
            </div>
            {(actionFilter !== 'all' || resourceFilter !== 'all' || statusFilter !== 'all' || fromDate || toDate) && (
              <button
                onClick={() => {
                  setActionFilter('all');
                  setResourceFilter('all');
                  setStatusFilter('all');
                  setFromDate('');
                  setToDate('');
                }}
                className="text-xs text-stone-400 hover:text-stone-600 dark:hover:text-stone-200 transition-colors py-1.5"
              >
                Limpiar filtros
              </button>
            )}
          </div>
        </Card>

        {/* Tabla */}
        <Card>
          <Table
            columns={columns}
            data={logs}
            isLoading={isLoading}
            emptyMessage="No hay registros de auditoría"
          />
          {pages > 0 && (
            <Pagination
              currentPage={page}
              totalPages={pages}
              onPageChange={setPage}
              onFirstPage={() => setPage(1)}
              onLastPage={() => setPage(pages)}
              onPreviousPage={() => setPage((p) => Math.max(1, p - 1))}
              onNextPage={() => setPage((p) => Math.min(pages, p + 1))}
              startIndex={startIndex}
              endIndex={endIndex}
              totalItems={total}
              itemsPerPage={pageSize}
              onItemsPerPageChange={(size) => setPageSize(size)}
            />
          )}
        </Card>
      </div>
    </DashboardLayout>
  );
}
