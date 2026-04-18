import { cn } from '@/lib/utils';

export type SkeletonVariant = 'card' | 'table-row' | 'detail' | 'widget';

interface SkeletonLoaderProps {
  variant: SkeletonVariant;
  count?: number;
  className?: string;
}

const SHIMMER = 'animate-pulse motion-reduce:animate-none bg-muted rounded-md';

function CardSkeleton() {
  return (
    <div data-testid="skeleton-item" className="rounded-lg border border-border p-4 space-y-3">
      <div className={cn(SHIMMER, 'h-4 w-3/4')} />
      <div className={cn(SHIMMER, 'h-3 w-1/2')} />
      <div className={cn(SHIMMER, 'h-3 w-2/3')} />
    </div>
  );
}

function TableRowSkeleton() {
  return (
    <div data-testid="skeleton-item" className="flex items-center gap-4 border-b border-border/50 px-4 py-3">
      <div className={cn(SHIMMER, 'h-4 flex-1')} />
      <div className={cn(SHIMMER, 'h-4 w-20')} />
      <div className={cn(SHIMMER, 'h-4 w-24')} />
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div data-testid="skeleton-item" className="space-y-4">
      <div className={cn(SHIMMER, 'h-8 w-1/2')} />
      <div className="space-y-2">
        <div className={cn(SHIMMER, 'h-4 w-full')} />
        <div className={cn(SHIMMER, 'h-4 w-5/6')} />
        <div className={cn(SHIMMER, 'h-4 w-4/6')} />
      </div>
      <div className={cn(SHIMMER, 'h-32 w-full')} />
    </div>
  );
}

function WidgetSkeleton() {
  return (
    <div data-testid="skeleton-item" className="rounded-lg border border-border p-4 space-y-2">
      <div className={cn(SHIMMER, 'h-3 w-24')} />
      <div className={cn(SHIMMER, 'h-8 w-16')} />
    </div>
  );
}

const VARIANT_MAP: Record<SkeletonVariant, () => JSX.Element> = {
  card: CardSkeleton,
  'table-row': TableRowSkeleton,
  detail: DetailSkeleton,
  widget: WidgetSkeleton,
};

export function SkeletonLoader({ variant, count = 1, className }: SkeletonLoaderProps) {
  const Item = VARIANT_MAP[variant];
  const items = Array.from({ length: count }, (_, i) => <Item key={i} />);

  return (
    <div
      data-testid="skeleton-loader"
      role="status"
      aria-label="Loading..."
      className={cn('space-y-3', className)}
    >
      {items}
    </div>
  );
}
