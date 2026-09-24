interface FilterOption {
  value: string;
  label: string;
}

interface FilterSelectProps {
  label: string;
  options: readonly FilterOption[];
  value: string;
  onChange: (value: string) => void;
}

export default function FilterSelect({ label, options, value, onChange }: FilterSelectProps) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs font-medium text-stone-500 dark:text-stone-400 whitespace-nowrap">
        {label}:
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="
          px-3 py-2 text-sm rounded-md border transition-colors duration-150
          bg-white dark:bg-stone-900
          text-stone-900 dark:text-stone-100
          border-stone-200 dark:border-stone-700
          hover:border-stone-300 dark:hover:border-stone-600
          focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500
        "
      >
        {options.map((option) => (
          <option
            key={option.value}
            value={option.value}
            className="bg-white dark:bg-stone-900 text-stone-900 dark:text-stone-100"
          >
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
