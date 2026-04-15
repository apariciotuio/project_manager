import { UserAvatar } from './user-avatar';
import { cn } from '@/lib/utils';
import { UserCircle } from 'lucide-react';

interface OwnerAvatarProps {
  name?: string;
  avatarUrl?: string | null;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  className?: string;
}

export function OwnerAvatar({ name, avatarUrl, size = 'sm', className }: OwnerAvatarProps) {
  if (!name) {
    return (
      <span
        role="img"
        aria-label="Sin asignar"
        className={cn('inline-flex items-center justify-center rounded-full bg-muted text-muted-foreground', className)}
      >
        <UserCircle className="h-4 w-4" aria-hidden />
      </span>
    );
  }

  return <UserAvatar name={name} avatarUrl={avatarUrl} size={size} className={className} />;
}
