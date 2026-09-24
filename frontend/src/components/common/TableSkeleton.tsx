import Skeleton from './Skeleton';

interface TableSkeletonProps {
  rows?: number;
  columns?: number;
}

export default function TableSkeleton({ rows = 5, columns = 4 }: TableSkeletonProps) {
  return (
    <div className="space-y-0">
      {/* Header */}
      <div className="flex items-center gap-4 px-5 py-3 bg-stone-50 dark:bg-stone-900/50 border-b border-stone-100 dark:border-stone-800">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} width="flex-1" height="h-3" />
        ))}
      </div>

      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex items-center gap-4 px-5 py-3.5 border-b border-stone-100 dark:border-stone-800"
        >
          {Array.from({ length: columns }).map((_, colIndex) => (
            <div key={colIndex} className="flex-1">
              {colIndex === 0 ? (
                <div className="flex items-center gap-3">
                  <Skeleton width="w-8" height="h-8" rounded="full" />
                  <Skeleton width="w-24" height="h-3" />
                </div>
              ) : (
                <Skeleton height="h-3" />
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
