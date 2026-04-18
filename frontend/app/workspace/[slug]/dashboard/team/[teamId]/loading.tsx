import { SkeletonLoader } from '@/components/layout/skeleton-loader';
import { PageContainer } from '@/components/layout/page-container';

export default function TeamDashboardLoading() {
  return (
    <PageContainer variant="wide">
      <SkeletonLoader variant="widget" count={4} />
    </PageContainer>
  );
}
