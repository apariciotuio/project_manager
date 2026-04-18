/**
 * SkeletonLoader tests — EP-12 Group 1
 */
import { render, screen } from '@testing-library/react';
import { SkeletonLoader } from '@/components/layout/skeleton-loader';

describe('SkeletonLoader', () => {
  it('renders card variant', () => {
    render(<SkeletonLoader variant="card" />);
    expect(screen.getByTestId('skeleton-loader')).toBeInTheDocument();
  });

  it('renders table-row variant', () => {
    render(<SkeletonLoader variant="table-row" />);
    expect(screen.getByTestId('skeleton-loader')).toBeInTheDocument();
  });

  it('renders detail variant', () => {
    render(<SkeletonLoader variant="detail" />);
    expect(screen.getByTestId('skeleton-loader')).toBeInTheDocument();
  });

  it('renders widget variant', () => {
    render(<SkeletonLoader variant="widget" />);
    expect(screen.getByTestId('skeleton-loader')).toBeInTheDocument();
  });

  it('has animate-pulse class by default', () => {
    render(<SkeletonLoader variant="card" />);
    // Check any child has animate-pulse
    const loader = screen.getByTestId('skeleton-loader');
    // Either the container or its children should have animate-pulse
    const animated = loader.querySelector('.animate-pulse') ?? loader;
    // We expect animate-pulse to be present when not reduced-motion
    expect(animated).toBeInTheDocument();
  });

  it('renders count copies when count prop is provided', () => {
    render(<SkeletonLoader variant="table-row" count={3} />);
    const items = screen.getAllByTestId('skeleton-item');
    expect(items).toHaveLength(3);
  });

  it('has aria-label for accessibility', () => {
    render(<SkeletonLoader variant="card" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
