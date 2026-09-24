import { useMemo } from 'react';

interface FilterConfig<T extends { is_active: boolean }> {
  data: T[];
  searchQuery: string;
  searchFields: string[];
  statusFilter: string;
  extraFilter?: (item: T) => boolean;
}

export function useFilteredData<T extends { is_active: boolean }>({
  data,
  searchQuery,
  searchFields,
  statusFilter,
  extraFilter,
}: FilterConfig<T>): T[] {
  return useMemo(() => {
    const q = searchQuery.toLowerCase();
    return data.filter((item) => {
      const record = item as Record<string, unknown>;
      const matchesSearch =
        q === '' ||
        searchFields.some((field) =>
          String(record[field] ?? '').toLowerCase().includes(q)
        );
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' && item.is_active) ||
        (statusFilter === 'inactive' && !item.is_active);
      return matchesSearch && matchesStatus && (!extraFilter || extraFilter(item));
    });
    // searchFields is a static constant defined outside the component
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, searchQuery, statusFilter, extraFilter]);
}
