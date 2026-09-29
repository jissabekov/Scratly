import Link from 'next/link';
import { api } from '../../lib/api';
import type { LearningHub } from '../../lib/types';
import { SessionBootstrap } from '../../components/learn/SessionBootstrap';
import { ModulePath } from '../../components/progress/ModulePath';

export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Learning path · Scratly',
};

/**
 * Learning hub (server component). Reads the session from `?session=` (set by
 * SessionBootstrap from localStorage) and renders the module path. All state
 * comes from FastAPI; nothing is persisted in the browser.
 */
export default async function ModulesPage({
  searchParams,
}: {
  searchParams: Promise<{ session?: string }>;
}) {
  const { session } = await searchParams;
  if (!session) {
    return <SessionBootstrap />;
  }

  let hub: LearningHub | null = null;
  try {
    hub = await api<LearningHub>(`/v1/sessions/${encodeURIComponent(session)}/learning`);
  } catch {
    hub = null;
  }

  if (hub === null) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 pb-32 pt-10">
        <h1 className="text-2xl font-semibold">Learning path</h1>
        <p className="mt-3 text-muted-foreground">
          We couldn&apos;t load this learning path. It may belong to a different session.
        </p>
        <p className="mt-4">
          <Link className="underline underline-offset-4" href="/">
            Back to the chat
          </Link>
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-32 pt-10">
      <header className="mb-2 flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Your learning path</h1>
          <p className="mt-2 text-muted-foreground">
            {hub.mastery_pct}% of lessons complete
            {hub.streak_days > 0 ? ` · ${hub.streak_days}-day streak` : ''}
          </p>
        </div>
        <Link
          href={`/progress?session=${encodeURIComponent(session)}`}
          className="shrink-0 text-sm text-muted-foreground underline underline-offset-4"
        >
          Progress →
        </Link>
      </header>
      {hub.modules.length === 0 ? (
        <p className="mt-4 text-muted-foreground">No modules are available yet.</p>
      ) : (
        <ModulePath hub={hub} sessionId={session} />
      )}
    </main>
  );
}
