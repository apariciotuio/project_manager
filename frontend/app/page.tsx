import { redirect } from 'next/navigation';

export default function HomePage(): never {
  // Middleware already redirects unauthenticated requests to /login.
  // Authenticated users land on workspace selection.
  redirect('/workspace/select');
}
