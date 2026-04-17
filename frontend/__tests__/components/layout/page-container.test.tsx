import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PageContainer } from '@/components/layout/page-container';

describe('PageContainer', () => {
  describe('variant="wide"', () => {
    it('renders children', () => {
      render(<PageContainer variant="wide"><p>Hello</p></PageContainer>);
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    it('applies max-w-screen-2xl class', () => {
      const { container } = render(
        <PageContainer variant="wide"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).toContain('max-w-screen-2xl');
    });

    it('applies mx-auto and w-full', () => {
      const { container } = render(
        <PageContainer variant="wide"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).toContain('mx-auto');
      expect(div.className).toContain('w-full');
    });

    it('applies wide padding classes', () => {
      const { container } = render(
        <PageContainer variant="wide"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      // px-4 on mobile, 2xl:px-16 (4rem) at ≥1440px
      expect(div.className).toContain('px-4');
      expect(div.className).toContain('2xl:px-16');
    });

    it('does NOT apply max-w-4xl class', () => {
      const { container } = render(
        <PageContainer variant="wide"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).not.toContain('max-w-4xl');
    });
  });

  describe('variant="narrow"', () => {
    it('applies max-w-4xl class', () => {
      const { container } = render(
        <PageContainer variant="narrow"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).toContain('max-w-4xl');
    });

    it('applies mx-auto and w-full', () => {
      const { container } = render(
        <PageContainer variant="narrow"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).toContain('mx-auto');
      expect(div.className).toContain('w-full');
    });

    it('does NOT apply max-w-screen-2xl', () => {
      const { container } = render(
        <PageContainer variant="narrow"><span>content</span></PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).not.toContain('max-w-screen-2xl');
    });
  });

  describe('className passthrough', () => {
    it('merges extra className onto the root element', () => {
      const { container } = render(
        <PageContainer variant="wide" className="flex flex-col gap-6">
          <span>x</span>
        </PageContainer>,
      );
      const div = container.firstChild as HTMLElement;
      expect(div.className).toContain('flex');
      expect(div.className).toContain('flex-col');
      expect(div.className).toContain('gap-6');
    });
  });
});
