import { cn } from '@/lib/utils';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg';

const SIZE_CLASSES: Record<AvatarSize, string> = {
  xs: 'h-6 w-6 text-xs',
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-body-sm',
  lg: 'h-12 w-12 text-body',
};

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return (parts[0]?.[0] ?? '').toUpperCase();
  return ((parts[0]?.[0] ?? '') + (parts[parts.length - 1]?.[0] ?? '')).toUpperCase();
}

interface UserAvatarProps {
  name: string;
  avatarUrl?: string | null;
  size?: AvatarSize;
  className?: string;
}

export function UserAvatar({ name, avatarUrl, size = 'md', className }: UserAvatarProps) {
  return (
    <Avatar
      role="img"
      aria-label={name}
      className={cn(SIZE_CLASSES[size], className)}
    >
      {avatarUrl && <AvatarImage src={avatarUrl} alt={name} />}
      <AvatarFallback>{getInitials(name)}</AvatarFallback>
    </Avatar>
  );
}
