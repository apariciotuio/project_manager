import { redirect } from 'next/navigation';

interface WorkspaceSlugPageProps {
  params: { slug: string };
}

export default function WorkspaceSlugPage({
  params: { slug },
}: WorkspaceSlugPageProps): never {
  redirect(`/workspace/${slug}/items`);
}
