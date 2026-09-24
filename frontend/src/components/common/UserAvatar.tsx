interface UserAvatarProps {
  initial: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeMap = {
  xs: 'w-7 h-7 text-xs font-semibold',
  sm: 'w-8 h-8 text-xs font-semibold',
  md: 'w-8 h-8 text-sm font-semibold',
  lg: 'w-16 h-16 text-2xl font-bold',
};

export default function UserAvatar({ initial, size = 'sm', className = '' }: UserAvatarProps) {
  return (
    <div
      className={`${sizeMap[size]} rounded-full bg-blue-600 flex items-center justify-center text-white shrink-0 ${className}`}
    >
      {initial}
    </div>
  );
}
