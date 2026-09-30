import { RouteBackLink } from '@/components/flow/RouteBackLink';
import { api } from '../../lib/api';
import type { CoachSummary } from '../../lib/types';
import { SessionBootstrap } from '../../components/learn/SessionBootstrap';
import { MasteryGrid } from '../../components/progress/MasteryGrid';

export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Progress · Scratly',
};

/**
 * Progress dashboard (server component). Mastery, streak, due retention, and
 * open interventions all come from FastAPI (`GET .../learning/summary`) — the
 * only state authority. Nothing is persisted in the browser.
 */
export default async function ProgressPage({
  searchParams,
}: {
  searchParams: Promise<{ session?: string }>;
}) {
  const { session } = await searchParams;
  if (!session) {
    return <SessionBootstrap />;
  }

  const hubHref = `/modules?session=${encodeURIComponent(session)}`;

  let summary: CoachSummary | null = null;
  try {
    summary = await api<CoachSummary>(
      `/v1/sessions/${encodeURIComponent(session)}/learning/summary`
    );
  } catch {
    summary = null;
  }

  if (summary === null) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 pb-10 pt-10">
        <RouteBackLink href={hubHref} label="Back to learning path" />
        <h1 className="mt-4 text-2xl font-semibold">Progress</h1>
        <p className="mt-3 text-muted-foreground">
          We couldn&apos;t load progress for this session.
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-10 pt-10">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <RouteBackLink href={hubHref} label="Back to learning path" className="-ml-3" />
          <h1 className="mt-2 text-2xl font-semibold">Progress</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Mastery, streaks, and what to revisit next.
          </p>
        </div>
      </header>

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-line bg-panel px-3 py-1 text-sm">
          {summary.streak_steps} step streak
        </span>
        <span className="rounded-full border border-line bg-panel px-3 py-1 text-sm text-muted-foreground">
          Check-ins {summary.checkins_used}/{summary.max_checkins}
        </span>
      </div>

      <section aria-labelledby="mastery-heading" className="mb-6">
        <h2 id="mastery-heading" className="text-lg font-semibold">
          Mastery by objective
        </h2>
        <MasteryGrid mastery={summary.mastery} />
      </section>

      <section aria-labelledby="retention-heading" className="mb-6">
        <h2 id="retention-heading" className="text-lg font-semibold">
          Due for review
        </h2>
        {summary.due_retention.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Nothing due yet — keep going and we&apos;ll bring these back later.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {summary.due_retention.map((card) => (
              <li
                key={card.objective_code}
                className="flex items-center justify-between rounded-md border border-line bg-panel px-3 py-2 text-sm"
              >
                <span>{card.objective_label || card.objective_code}</span>
                <span className="text-muted-foreground">
                  {card.overdue ? 'overdue' : `in ${card.interval_days}d`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="advice-heading">
        <h2 id="advice-heading" className="text-lg font-semibold">
          Advice
        </h2>
        {summary.open_interventions.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            No advice right now — you&apos;re on track.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {summary.open_interventions.map((item) => (
              <li
                key={item.id}
                className="rounded-md border border-line bg-panel px-3 py-2 text-sm"
              >
                <span className="mr-2 rounded-full border border-line px-2 py-0.5 text-xs uppercase tracking-wide text-muted-foreground">
                  {item.level}
                </span>
                {item.summary || item.trigger_rule}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
