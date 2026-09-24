import { TableColumn, TableAction } from '@/types';
import Button from './Button';
import ProtectedComponent from './ProtectedComponent';
import TableSkeleton from './TableSkeleton';

interface TableProps<T> {
  data: T[];
  columns: TableColumn<T>[];
  actions?: TableAction<T>[];
  isLoading?: boolean;
  emptyMessage?: string;
}

export default function Table<T extends { id: number | string }>({
  data,
  columns,
  actions = [],
  isLoading = false,
  emptyMessage = 'No hay datos para mostrar',
}: TableProps<T>) {
  if (isLoading) {
    return <TableSkeleton rows={5} columns={columns.length + (actions.length > 0 ? 1 : 0)} />;
  }

  if (data.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-stone-400 dark:text-stone-500">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto -mx-5 sm:mx-0">
      <table className="min-w-full divide-y divide-stone-100 dark:divide-stone-800">
        <thead>
          <tr>
            {columns.map((column, index) => (
              <th
                key={index}
                className="px-4 py-3 text-left text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider bg-stone-50 dark:bg-stone-900/50 first:pl-5 last:pr-5"
              >
                {column.label}
              </th>
            ))}
            {actions.length > 0 && (
              <th className="px-4 py-3 text-right text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider bg-stone-50 dark:bg-stone-900/50 last:pr-5">
                Acciones
              </th>
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
          {data.map((item) => (
            <tr
              key={item.id}
              className="hover:bg-stone-50 dark:hover:bg-stone-800/40 transition-colors"
            >
              {columns.map((column, colIndex) => (
                <td
                  key={colIndex}
                  className="px-4 py-3 text-sm text-stone-700 dark:text-stone-300 first:pl-5 last:pr-5"
                >
                  {column.render
                    ? column.render(item)
                    : String((item as Record<string, unknown>)[column.key as string] ?? '')}
                </td>
              ))}
              {actions.length > 0 && (
                <td className="px-4 py-3 last:pr-5">
                  <div className="flex items-center justify-end gap-1.5">
                    {actions.map((action, actionIndex) => (
                      <ProtectedComponent
                        key={actionIndex}
                        permissions={action.permission ? [action.permission] : []}
                      >
                        <Button
                          size="sm"
                          variant={action.variant || 'ghost'}
                          onClick={() => action.onClick(item)}
                          title={action.label}
                        >
                          {action.icon ?? action.label}
                        </Button>
                      </ProtectedComponent>
                    ))}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
