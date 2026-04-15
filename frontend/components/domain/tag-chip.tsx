import { cn } from '@/lib/utils';
import { pickContrastColor, hexToRgb } from '@/lib/color';

export interface Tag {
  id: string;
  name: string;
  color: string;
}

interface TagChipProps {
  tag: Tag;
  onClick?: (tag: Tag) => void;
  onRemove?: (tag: Tag) => void;
  className?: string;
}

function tagBackgroundStyle(color: string): React.CSSProperties {
  const rgb = hexToRgb(color);
  if (!rgb) return { backgroundColor: 'hsl(var(--muted))', color: 'hsl(var(--muted-foreground))' };

  const textColor = pickContrastColor(color);
  return {
    backgroundColor: `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.15)`,
    color: textColor === '#ffffff' ? 'hsl(var(--foreground))' : color,
    borderColor: `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4)`,
  };
}

export function TagChip({ tag, onClick, onRemove, className }: TagChipProps) {
  const style = tagBackgroundStyle(tag.color);

  const baseClass = cn(
    'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-colors',
    className
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={() => onClick(tag)}
        style={style}
        className={cn(baseClass, 'hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1')}
      >
        {tag.name}
        {onRemove && (
          <span
            role="button"
            aria-label={`Quitar etiqueta ${tag.name}`}
            onClick={(e) => { e.stopPropagation(); onRemove(tag); }}
            className="ml-0.5 cursor-pointer opacity-70 hover:opacity-100"
          >
            ×
          </span>
        )}
      </button>
    );
  }

  return (
    <span style={style} className={baseClass}>
      {tag.name}
    </span>
  );
}
