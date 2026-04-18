import { SkeletonLoader } from '@/components/layout/skeleton-loader';

export default function Loading() {
  return <SkeletonLoader variant="widget" count={4} />;
}
