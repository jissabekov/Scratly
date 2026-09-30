import { Suspense } from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { api } from '../../../../lib/api';
import type { LearningHub, QuizDraw } from '../../../../lib/types';
import { QuizRunner } from '../../../../components/learn/QuizRunner';
import { SessionBootstrap } from '../../../../components/learn/SessionBootstrap';
import { RouteBackLink } from '../../../../components/flow/RouteBackLink';

export const dynamic = 'force-dynamic';

function GateNotice({
  title,
  body,
  hubHref,
  extra,
}: {
  title: string;
  body: string;
  hubHref: string;
  extra?: React.ReactNode;
}) {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-10">
      <RouteBackLink href={hubHref} label="Back to learning path" />
      <h1 className="mt-4 text-2xl font-semibold">{title}</h1>
      <p className="mt-3 text-muted-foreground">{body}</p>
      {extra}
    </main>
  );
}

/**
 * Module quiz (server component). The draw creates or resumes the open attempt
 * server-side; the player itself is a client leaf. Position is `?q=`.
 */
export default async function ModuleQuizPage({
  params,
  searchParams,
}: {
  params: Promise<{ moduleId: string }>;
  searchParams: Promise<{ session?: string; q?: string }>;
}) {
  const { moduleId } = await params;
  const { session } = await searchParams;
  if (!session) {
    return <SessionBootstrap />;
  }

  const hubHref = `/modules?session=${encodeURIComponent(session)}`;
  const encodedSession = encodeURIComponent(session);
  const encodedModule = encodeURIComponent(moduleId);

  let hub: LearningHub | null = null;
  let draw: QuizDraw | null = null;
  try {
    hub = await api<LearningHub>(`/v1/sessions/${encodedSession}/learning`);
    draw = await api<QuizDraw>(
      `/v1/sessions/${encodedSession}/learning/modules/${encodedModule}/quiz`
    );
  } catch {
    hub = null;
    draw = null;
  }
  if (hub === null || draw === null) {
    notFound();
  }

  const summary = hub.modules.find((module) => module.id === moduleId) ?? null;
  const position = hub.modules.findIndex((module) => module.id === moduleId);
  const next = position >= 0 ? hub.modules[position + 1] : undefined;
  const nextModuleHref = next ? `/modules/${next.id}?session=${encodedSession}&slide=1` : null;
  const reviewHref = `/modules/${encodedModule}?session=${encodedSession}`;

  if (draw.gate === 'available' && draw.attempt) {
    return (
      <Suspense fallback={null}>
        <QuizRunner
          sessionId={session}
          moduleId={moduleId}
          moduleTitle={summary?.title ?? 'Module'}
          attempt={draw.attempt}
          maxAttempts={draw.max_attempts}
          nextModuleHref={nextModuleHref}
          hubHref={hubHref}
        />
      </Suspense>
    );
  }

  if (draw.gate === 'passed') {
    return (
      <GateNotice
        title="Quiz already passed"
        body={`You have cleared ${summary?.title ?? 'this module'}.`}
        hubHref={hubHref}
        extra={
          nextModuleHref ? (
            <p className="mt-4">
              <Link
                className="inline-block border border-primary bg-accent px-4 py-2 text-sm font-medium"
                href={nextModuleHref}
              >
                Start the next module
              </Link>
            </p>
          ) : null
        }
      />
    );
  }

  if (draw.gate === 'cooldown') {
    const minutes = Math.ceil((draw.retry_after_seconds ?? 0) / 60);
    return (
      <GateNotice
        title="Take a short break"
        body={`Review the slides that cover what you missed, then come back in about ${minutes} minute${
          minutes === 1 ? '' : 's'
        } for the alternate form.`}
        hubHref={hubHref}
        extra={
          <p className="mt-4">
            <Link className="underline underline-offset-4" href={reviewHref}>
              Review the module slides
            </Link>
          </p>
        }
      />
    );
  }

  if (draw.gate === 'handoff') {
    return (
      <GateNotice
        title="Let us get some help with this one"
        body="You have used all three attempts, so this is a good moment to go through it with a teacher or mentor. Bring the slides below to the conversation."
        hubHref={hubHref}
        extra={
          <p className="mt-4">
            <Link className="underline underline-offset-4" href={reviewHref}>
              Review the module slides
            </Link>
          </p>
        }
      />
    );
  }

  return (
    <GateNotice
      title="Quiz not available yet"
      body="Finish the module slides first — the quiz unlocks after the last slide."
      hubHref={hubHref}
    />
  );
}
