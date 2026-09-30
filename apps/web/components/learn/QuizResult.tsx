'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'motion/react';
import { CheckCircle2, RotateCcw, Users } from 'lucide-react';
import { RouteBackLink } from '@/components/flow/RouteBackLink';
import type { QuizAttemptResult } from '@/lib/types';

const NEXT_ACTION_COPY: Record<QuizAttemptResult['next_action'], string> = {
  unlock_next: '',
  retry: 'You are close. Review the slides below, then take the alternate form — the questions change each attempt.',
  walkthrough:
    'Let us walk through the tricky parts together before the next attempt. Start with the review slides below.',
  handoff:
    'This is a good moment to talk it through with a teacher or mentor. Bring the review slides below to the conversation.',
};

export type QuizResultProps = {
  sessionId: string;
  moduleId: string;
  moduleTitle: string;
  result: QuizAttemptResult;
  nextModuleHref: string | null;
  hubHref: string;
};

function reviewHref(sessionId: string, moduleId: string, slide: number): string {
  return `/modules/${moduleId}?session=${encodeURIComponent(sessionId)}&slide=${slide}`;
}

/** Pass unlocks the next module; fail lists what to review with deep links. */
export function QuizResult({
  sessionId,
  moduleId,
  moduleTitle,
  result,
  nextModuleHref,
  hubHref,
}: QuizResultProps) {
  const reduced = useReducedMotion();
  const quizHref = `/modules/${moduleId}/quiz?session=${encodeURIComponent(sessionId)}`;

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-8">
      <motion.section
        role="status"
        aria-live="polite"
        initial={reduced ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className={
          result.passed
            ? 'border border-primary bg-accent p-6 text-center'
            : 'border border-line bg-panel p-6 text-center'
        }
      >
        <p className="text-lg font-semibold">
          {result.passed
            ? `Quiz passed — ${result.score}/${result.item_count}`
            : `${result.score}/${result.item_count} — not passed yet`}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {result.passed
            ? `You cleared ${moduleTitle}${result.critical_missed.length === 0 ? ' on every critical objective' : ''}.`
            : `You need ${result.threshold} of ${result.item_count}, including at least one on every critical objective.`}
        </p>
        {result.next_action !== 'unlock_next' ? (
          <p className="mx-auto mt-3 max-w-xl text-sm">{NEXT_ACTION_COPY[result.next_action]}</p>
        ) : null}
      </motion.section>

      {result.missed.length > 0 ? (
        <section className="mt-6">
          <h2 className="text-base font-semibold">Worth another look</h2>
          <ul className="mt-3 flex flex-col gap-3">
            {result.missed.map((missed) => (
              <li key={missed.item_id} className="border border-line bg-panel p-4">
                <p className="text-sm font-medium">{missed.stem}</p>
                <p className="mt-1 text-sm text-muted-foreground">{missed.feedback_wrong}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Objective: {missed.objective_code}
                </p>
                {missed.slide_ref !== null ? (
                  <Link
                    href={reviewHref(sessionId, moduleId, missed.slide_ref)}
                    className="mt-2 inline-block text-sm underline underline-offset-4"
                  >
                    Review slide {missed.slide_ref}
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {result.remediation && result.remediation.slide_refs.length > 0 ? (
        <section className="mt-6 border border-line bg-panel p-4">
          <h2 className="text-base font-semibold">Re-teach before you retry</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            These slides cover the objectives you missed:
          </p>
          <ul className="mt-2 flex flex-wrap gap-3">
            {result.remediation.slide_refs.map((slide) => (
              <li key={slide}>
                <Link
                  href={reviewHref(sessionId, moduleId, slide)}
                  className="text-sm underline underline-offset-4"
                >
                  Slide {slide}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center gap-4">
        {result.passed ? (
          nextModuleHref ? (
            <Link
              href={nextModuleHref}
              className="inline-flex items-center gap-2 border border-primary bg-accent px-4 py-2 text-sm font-medium"
            >
              <CheckCircle2 className="size-4" aria-hidden="true" />
              Start the next module
            </Link>
          ) : null
        ) : result.next_action === 'handoff' ? (
          <p className="inline-flex items-center gap-2 text-sm">
            <Users className="size-4" aria-hidden="true" />
            Handoff card created — bring this to your teacher or mentor.
          </p>
        ) : (
          <Link
            href={quizHref}
            className="inline-flex items-center gap-2 border border-primary bg-accent px-4 py-2 text-sm font-medium"
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            Try form {result.next_form_id ?? '2'}
          </Link>
        )}
        <RouteBackLink href={hubHref} label="Back to learning path" />
      </div>
    </main>
  );
}
