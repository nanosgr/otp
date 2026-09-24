import { useState, useEffect } from 'react';
import { Search, X } from 'lucide-react';

interface SearchBarProps {
  placeholder?: string;
  onSearch: (query: string) => void;
  debounceMs?: number;
}

export default function SearchBar({
  placeholder = 'Buscar...',
  onSearch,
  debounceMs = 300,
}: SearchBarProps) {
  const [query, setQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => { onSearch(query); }, debounceMs);
    return () => clearTimeout(timer);
  }, [query, debounceMs, onSearch]);

  return (
    <div className="relative">
      <Search className="absolute inset-y-0 left-3 my-auto w-4 h-4 text-stone-400 dark:text-stone-500 pointer-events-none" />
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="
          w-full pl-9 pr-8 py-2 text-sm rounded-md border transition-colors duration-150
          bg-white dark:bg-stone-900
          text-stone-900 dark:text-stone-100
          placeholder:text-stone-400 dark:placeholder:text-stone-600
          border-stone-200 dark:border-stone-700
          hover:border-stone-300 dark:hover:border-stone-600
          focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500
        "
        placeholder={placeholder}
      />
      {query && (
        <button
          onClick={() => setQuery('')}
          className="absolute inset-y-0 right-2 my-auto p-0.5 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
