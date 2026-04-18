import { SkeletonLoader } from '@/components/layout/skeleton-loader';

export default function Loading() {
  return <SkeletonLoader variant="table-row" count={8} />;
}
