import { TagChip, type Tag } from './tag-chip';
import { cn } from '@/lib/utils';

interface TagChipListProps {
  tags: Tag[];
  max?: number;
  onTagClick?: (tag: Tag) => void;
  onTagRemove?: (tag: Tag) => void;
  className?: string;
}

export function TagChipList({
  tags,
  max = 5,
  onTagClick,
  onTagRemove,
  className,
}: TagChipListProps) {
  const visible = tags.slice(0, max);
  const overflow = tags.length - visible.length;

  return (
    <div className={cn('flex flex-wrap items-center gap-1', className)}>
      {visible.map((tag) => (
        <TagChip
          key={tag.id}
          tag={tag}
          onClick={onTagClick}
          onRemove={onTagRemove}
        />
      ))}
      {overflow > 0 && (
        <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          +{overflow}
        </span>
      )}
    </div>
  );
}
