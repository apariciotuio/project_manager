import { describe, it, expect, vi } from 'vitest';
import WorkspaceSlugPage from '@/app/workspace/[slug]/page';

const redirectMock = vi.fn();

vi.mock('next/navigation', () => ({
  redirect: (url: string) => {
    redirectMock(url);
    throw new Error('NEXT_REDIRECT'); // mimic next/navigation behavior
  },
}));

describe('WorkspaceSlugPage', () => {
  it('redirects /workspace/{slug} to the items view', () => {
    expect(() => WorkspaceSlugPage({ params: { slug: 'acme' } })).toThrow(
      'NEXT_REDIRECT',
    );
    expect(redirectMock).toHaveBeenCalledWith('/workspace/acme/items');
  });
});
