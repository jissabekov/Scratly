'use client';

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { FlowActionBar } from '@/components/flow/FlowActionBar';
import { RouteBackLink } from '@/components/flow/RouteBackLink';
import { SlideProgress } from '@/components/flow/SlideProgress';
import { checkQuizItemAction, submitQuizAttemptAction } from '@/lib/actions';
import { newIdempotencyKey } from '@/lib/session';
import { cn } from '@/lib/utils';
import type { QuizAttemptResult, QuizAttemptView } from '@/lib/types';
import { QuizResult } from './QuizResult';

export type QuizRunnerProps = {
  sessionId: string;
  moduleId: string;
  moduleTitle: string;
  attempt: QuizAttemptView;
  maxAttempts: number;
  nextModuleHref: string | null;
  hubHref: string;
};

type Feedback = { correct: boolean; feedback: string };

/**
 * One question at a time (`?q=`). Answers are checked server-side for
 * immediate feedback; the attempt is scored at the end by the API. Keyboard:
 * 1–4 pick options, Enter is the primary CTA, ←/→ move between questions.
 */
export function QuizRunner({
  sessionId,
  moduleId,
  moduleTitle,
  attempt,
  maxAttempts,
  nextModuleHref,
  hubHref,
}: QuizRunnerProps) {
  const router = useRouter();
  const total = attempt.items.length;
  const reduced = useReducedMotion();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const indexRef = useRef(1);

  const [index, setIndexState] = useState(1);
  const [responses, setResponses] = useState<Record<string, string[]>>({});
  const [feedback, setFeedback] = useState<Record<string, Feedback>>({});
  const [result, setResult] = useState<QuizAttemptResult | null>(null);
  const [error, setError] = useState('');
  const [pending, startTransition] = useTransition();

  const item = attempt.items[Math.min(index, total) - 1];
  const selected = useMemo(() => responses[item?.id] ?? [], [responses, item?.id]);
  const checked = feedback[item?.id];
  const isLast = index >= total;
  const isMulti = item?.kind === 'select_all';

  const leaveToHub = useCallback(() => {
    router.push(hubHref);
  }, [hubHref, router]);

  const setIndex = useCallback(
    (next: number) => {
      const clamped = Math.min(Math.max(next, 1), total);
      setIndexState(clamped);
      const url = new URL(window.location.href);
      url.searchParams.set('q', String(clamped));
      window.history.pushState({ q: clamped }, '', url);
    },
    [total]
  );

  useEffect(() => {
    indexRef.current = index;
    headingRef.current?.focus();
  }, [index]);

  useEffect(() => {
    const onPopState = () => {
      const raw = new URL(window.location.href).searchParams.get('q');
      const parsed = raw ? Number.parseInt(raw, 10) : Number.NaN;
      if (Number.isFinite(parsed)) setIndexState(Math.min(Math.max(parsed, 1), total));
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [total]);

  const runCheck = useCallback(
    (itemId: string, response: string[]) => {
      if (response.length === 0) return;
      startTransition(async () => {
        try {
          const check = await checkQuizItemAction({
            sessionId,
            attemptId: attempt.attempt_id,
            itemId,
            response,
            latencyMs: null,
          });
          setFeedback((prev) => ({
            ...prev,
            [itemId]: { correct: check.correct, feedback: check.feedback },
          }));
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    },
    [attempt.attempt_id, sessionId]
  );

  const choose = useCallback(
    (key: string) => {
      if (!item) return;
      const next = isMulti
        ? selected.includes(key)
          ? selected.filter((value) => value !== key)
          : [...selected, key]
        : [key];
      setResponses((prev) => ({ ...prev, [item.id]: next }));
      if (!isMulti) runCheck(item.id, next);
    },
    [item, isMulti, selected, runCheck]
  );

  const finish = useCallback(() => {
    startTransition(async () => {
      try {
        const submitted = await submitQuizAttemptAction({
          sessionId,
          moduleId,
          attemptId: attempt.attempt_id,
          requestId: newIdempotencyKey(),
          responses: attempt.items.map((entry) => ({
            item_id: entry.id,
            response: responses[entry.id] ?? [],
            latency_ms: null,
          })),
        });
        setResult(submitted);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }, [attempt, moduleId, responses, sessionId]);

  const advance = useCallback(() => {
    if (!item || pending) return;
    if (!checked) {
      runCheck(item.id, selected);
      return;
    }
    if (isLast) finish();
    else setIndex(index + 1);
  }, [checked, finish, index, isLast, item, pending, runCheck, selected, setIndex]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
        if (event.key === 'Enter') {
          event.preventDefault();
          advance();
        }
        return;
      }
      if (event.key === 'Enter') {
        event.preventDefault();
        advance();
      } else if (event.key === 'ArrowRight' && checked && !isLast) {
        event.preventDefault();
        setIndex(index + 1);
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        if (index > 1) setIndex(index - 1);
        else leaveToHub();
      } else if (/^[1-4]$/.test(event.key) && item) {
        const option = item.options[Number(event.key) - 1];
        if (option) {
          event.preventDefault();
          choose(option.key);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [advance, checked, choose, index, isLast, item, leaveToHub, setIndex]);

  const primaryLabel = useMemo(() => {
    if (!checked) return 'Check answer';
    return isLast ? 'See results' : 'Next';
  }, [checked, isLast]);

  if (result) {
    return (
      <QuizResult
        sessionId={sessionId}
        moduleId={moduleId}
        moduleTitle={moduleTitle}
        result={result}
        nextModuleHref={nextModuleHref}
        hubHref={hubHref}
      />
    );
  }

  if (!item) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 pt-10">
        <RouteBackLink href={hubHref} label="Back to learning path" />
        <p className="mt-4 text-muted-foreground">This quiz has no questions.</p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-28 pt-6">
      <div className="mb-4 flex items-center gap-3">
        <RouteBackLink href={hubHref} label="Back to learning path" className="-ml-3 shrink-0" />
        <div className="flex-1">
          <SlideProgress current={index} total={total} label={`Question ${index} of ${total}`} />
        </div>
      </div>

      <p className="font-[family-name:var(--font-body)] text-xs tracking-wide text-muted-foreground">
        {moduleTitle} · attempt {attempt.attempt_no} of {maxAttempts} · form {attempt.form_id}
      </p>
      <h2
        ref={headingRef}
        tabIndex={-1}
        className="mt-1 font-[family-name:var(--font-display)] text-xl font-semibold outline-none"
      >
        Question {index} of {total}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{attempt.pass_rule}</p>

      <div className="relative mt-5 min-h-64">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={item.id}
            initial={reduced ? false : { opacity: 0, x: 32 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduced ? undefined : { opacity: 0, x: -32 }}
            transition={{ duration: reduced ? 0 : 0.2 }}
            className="flex flex-col gap-4"
          >
            <fieldset data-testid="quiz-question" className="border border-line bg-panel p-4">
              <legend className="text-sm font-semibold">{item.stem}</legend>
              <div className="mt-3 flex flex-col gap-2">
                {item.options.map((option) => {
                  const isSelected = selected.includes(option.key);
                  const showRight = checked && isSelected && checked.correct;
                  const showWrong = checked && isSelected && !checked.correct;
                  return (
                    <label
                      key={option.key}
                      className={cn(
                        'flex cursor-pointer items-start gap-3 border p-3 text-sm',
                        showRight && 'border-success bg-success-tint',
                        showWrong && 'border-warn bg-warning-tint',
                        !isSelected && 'border-line hover:border-primary'
                      )}
                    >
                      <input
                        type={isMulti ? 'checkbox' : 'radio'}
                        name={item.id}
                        value={option.key}
                        checked={isSelected}
                        onChange={() => choose(option.key)}
                        className="mt-0.5 size-4 shrink-0 accent-primary"
                      />
                      <span>{option.label}</span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
            <p
              role="status"
              aria-live="polite"
              className={cn('text-sm', checked?.correct ? 'text-success' : 'text-warn')}
            >
              {checked ? `${checked.correct ? 'Correct.' : 'Not quite.'} ${checked.feedback}` : ''}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>

      {error ? (
        <p role="alert" className="mt-4 text-sm text-warn">
          {error}
        </p>
      ) : null}

      <FlowActionBar
        onBack={index > 1 ? () => setIndex(index - 1) : leaveToHub}
        backLabel="Back"
        primaryLabel={primaryLabel}
        onPrimary={advance}
        primaryDisabled={!checked && selected.length === 0}
        pending={pending}
      />
    </main>
  );
}
