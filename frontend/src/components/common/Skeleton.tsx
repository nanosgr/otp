interface SkeletonProps {
  className?: string;
  width?: string;
  height?: string;
  rounded?: 'sm' | 'md' | 'lg' | 'full';
}

export default function Skeleton({
  className = '',
  width = 'w-full',
  height = 'h-4',
  rounded = 'md'
}: SkeletonProps) {
  const roundedClasses = {
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    full: 'rounded-full',
  };

  return (
    <div
      className={`${width} ${height} ${roundedClasses[rounded]} bg-stone-200 dark:bg-stone-700 animate-pulse ${className}`}
    />
  );
}
