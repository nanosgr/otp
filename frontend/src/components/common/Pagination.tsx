interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onFirstPage: () => void;
  onLastPage: () => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
  startIndex: number;
  endIndex: number;
  totalItems: number;
  itemsPerPage: number;
  onItemsPerPageChange: (items: number) => void;
}

export default function Pagination({
  currentPage, totalPages, onPageChange,
  onFirstPage, onLastPage, onPreviousPage, onNextPage,
  startIndex, endIndex, totalItems, itemsPerPage, onItemsPerPageChange,
}: PaginationProps) {
  const itemsPerPageOptions = [10, 25, 50, 100];

  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisible = 5;
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push('...');
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      for (let i = start; i <= end; i++) pages.push(i);
      if (currentPage < totalPages - 2) pages.push('...');
      if (totalPages > 1) pages.push(totalPages);
    }
    return pages;
  };

  if (totalPages === 0) return null;

  const navBtn = (disabled: boolean) =>
    `px-2.5 py-1 rounded-md text-sm font-medium transition-colors ${
      disabled
        ? 'text-stone-300 dark:text-stone-600 cursor-not-allowed'
        : 'text-stone-500 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800 hover:text-stone-800 dark:hover:text-stone-200'
    }`;

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mt-5 pt-4 border-t border-stone-100 dark:border-stone-800">
      {/* Items per page */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-stone-500 dark:text-stone-400">Mostrar:</label>
        <select
          value={itemsPerPage}
          onChange={(e) => onItemsPerPageChange(Number(e.target.value))}
          className="
            px-2 py-1 text-xs rounded-md border transition-colors
            bg-white dark:bg-stone-900
            text-stone-700 dark:text-stone-300
            border-stone-200 dark:border-stone-700
            focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500
          "
        >
          {itemsPerPageOptions.map((opt) => (
            <option key={opt} value={opt} className="bg-white dark:bg-stone-900">
              {opt}
            </option>
          ))}
        </select>
        <span className="text-xs text-stone-500 dark:text-stone-400">por página</span>
      </div>

      {/* Info */}
      <p className="text-xs text-stone-500 dark:text-stone-400 tabular-nums">
        <span className="font-medium text-stone-700 dark:text-stone-300">{startIndex}–{endIndex}</span>
        {' '}de{' '}
        <span className="font-medium text-stone-700 dark:text-stone-300">{totalItems}</span>
      </p>

      {/* Controls */}
      <div className="flex items-center gap-0.5">
        <button onClick={onFirstPage} disabled={currentPage === 1} className={navBtn(currentPage === 1)} title="Primera página">⟪</button>
        <button onClick={onPreviousPage} disabled={currentPage === 1} className={navBtn(currentPage === 1)} title="Anterior">‹</button>

        {getPageNumbers().map((page, i) =>
          page === '...' ? (
            <span key={`e-${i}`} className="px-2 py-1 text-xs text-stone-400 dark:text-stone-600">…</span>
          ) : (
            <button
              key={page}
              onClick={() => onPageChange(page as number)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                currentPage === page
                  ? 'bg-stone-900 dark:bg-stone-100 text-white dark:text-stone-900'
                  : 'text-stone-600 dark:text-stone-400 hover:bg-stone-100 dark:hover:bg-stone-800'
              }`}
            >
              {page}
            </button>
          )
        )}

        <button onClick={onNextPage} disabled={currentPage === totalPages} className={navBtn(currentPage === totalPages)} title="Siguiente">›</button>
        <button onClick={onLastPage} disabled={currentPage === totalPages} className={navBtn(currentPage === totalPages)} title="Última página">⟫</button>
      </div>
    </div>
  );
}
