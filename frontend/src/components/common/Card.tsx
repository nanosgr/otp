interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
  actions?: React.ReactNode;
}

export default function Card({ title, children, className = '', actions }: CardProps) {
  return (
    <div className={`bg-white dark:bg-stone-900 rounded-lg border border-stone-200 dark:border-stone-800 transition-colors ${className}`}>
      {(title || actions) && (
        <div className="px-5 py-3.5 border-b border-stone-100 dark:border-stone-800 flex items-center justify-between">
          {title && (
            <h3 className="text-sm font-semibold text-stone-700 dark:text-stone-200">{title}</h3>
          )}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  );
}
