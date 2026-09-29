'use client';

import { useCallback, useEffect, useRef, useState, useTransition } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { CheckCircle2, Info, X } from 'lucide-react';
import { deliverCheckinAction, dismissCheckinAction, respondCheckinAction } from '@/lib/actions';
import { newIdempotencyKey } from '@/lib/session';
import type { CheckinItemView, CheckinResult } from '@/lib/types';

export type CheckInWidgetProps = {
  sessionId: string;
  /** Called when the widget is answered or dismissed so the host can react. */
  onSettled?: (outcome: 'answered' | 'dismissed') => void;
  className?: string;
};

/**
 * Non-modal, dismissible progress check-in card (Plan 05 W5.4).
 *
 * Scheduling and scoring are deterministic and owned by the API; this component
 * only presents the delivered item and posts the answer. It never persists
 * progress locally and never blocks the lesson: "Not now" dismisses it and the
 * API doubles the cooldown. Keyboard: 1–5 select an option, Enter submits.
 */
export function CheckInWidget({ sessionId, onSettled, className }: CheckInWidgetProps) {
  const reduced = useReducedMotion();
  const [item, setItem] = useState<CheckinItemView | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [freeText, setFreeText] = useState('');
  const [result, setResult] = useState<CheckinResult | null>(null);
  const [note, setNote] = useState('');
  const [hidden, setHidden] = useState(false);
  const [error, setError] = useState('');
  const [pending, startTransition] = useTransition();

  const headingRef = useRef<HTMLHeadingElement>(null);
  const openedAtRef = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    deliverCheckinAction({ sessionId })
      .then((delivered) => {
        if (cancelled) return;
        if (delivered.gate === 'available' && delivered.item) {
          setItem(delivered.item);
          openedAtRef.current = Date.now();
        } else {
          setNote(gateNote(delivered.gate, delivered.retry_after_seconds));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (item) headingRef.current?.focus();
  }, [item]);

  const submit = useCallback(() => {
    if (!item || pending) return;
    const response = item.kind === 'likert' || item.kind === 'mcq' ? selected : [];
    startTransition(async () => {
      try {
        const answered = await respondCheckinAction({
          sessionId,
          checkinId: item.id,
          requestId: newIdempotencyKey(),
          response,
          freeText,
          latencyMs: Date.now() - openedAtRef.current,
        });
        setResult(answered);
        onSettled?.('answered');
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }, [item, pending, selected, freeText, sessionId, onSettled]);

  const dismiss = useCallback(() => {
    if (!item || pending) return;
    startTransition(async () => {
      try {
        await dismissCheckinAction({
          sessionId,
          checkinId: item.id,
          requestId: newIdempotencyKey(),
          reason: 'student_declined',
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setHidden(true);
        onSettled?.('dismissed');
      }
    });
  }, [item, pending, sessionId, onSettled]);

  const choose = useCallback((key: string) => setSelected([key]), []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!item || result || hidden) return;
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT')) {
        return;
      }
      if (/^[1-5]$/.test(event.key)) {
        const option = item.options[Number(event.key) - 1];
        if (option) {
          event.preventDefault();
          choose(option.key);
        }
      } else if (event.key === 'Enter' && (item.kind === 'likert' || item.kind === 'mcq')) {
        event.preventDefault();
        submit();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [item, result, hidden, choose, submit]);

  if (hidden) return null;
  if (error) {
    return (
      <p role="alert" className={`text-sm text-warn ${className ?? ''}`}>
        {error}
      </p>
    );
  }
  if (!item) {
    return note ? (
      <p role="status" aria-live="polite" className={`text-xs text-muted-foreground ${className ?? ''}`}>
        {note}
      </p>
    ) : null;
  }

  const canSubmit =
    item.kind === 'likert' || item.kind === 'mcq'
      ? selected.length > 0
      : freeText.trim().length >= 3;

  return (
    <motion.section
      aria-labelledby="checkin-heading"
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={reduced ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.2 }}
      className={`rounded-lg border border-line bg-panel p-4 ${className ?? ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Info aria-hidden="true" className="size-4 text-muted-foreground" />
          <p className="text-xs tracking-wide text-muted-foreground uppercase">
            Quick check-in · {item.objective_label}
          </p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          disabled={pending}
          className="rounded-md p-1 text-muted-foreground hover:text-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          aria-label="Dismiss check-in"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      </div>

      <h3 id="checkin-heading" ref={headingRef} tabIndex={-1} className="mt-2 text-base font-semibold outline-none">
        {item.prompt}
      </h3>

      {item.kind === 'likert' && item.scale ? (
        <fieldset className="mt-3">
          <legend className="sr-only">{item.prompt}</legend>
          <div role="radiogroup" aria-label={item.prompt} className="flex flex-wrap gap-2">
            {likertValues(item.scale.min, item.scale.max).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={selected[0] === String(value)}
                onClick={() => choose(String(value))}
                className={`min-w-10 rounded-md border px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                  selected[0] === String(value)
                    ? 'border-accent bg-accent text-paper'
                    : 'border-line bg-paper hover:border-accent'
                }`}
              >
                {value}
              </button>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-xs text-muted-foreground">
            <span>{item.scale.low_label}</span>
            <span>{item.scale.high_label}</span>
          </div>
        </fieldset>
      ) : null}

      {item.kind === 'mcq' ? (
        <fieldset className="mt-3">
          <legend className="sr-only">{item.prompt}</legend>
          <div role="radiogroup" aria-label={item.prompt} className="flex flex-col gap-2">
            {item.options.map((option, index) => (
              <label
                key={option.key}
                className={`flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 text-sm ${
                  selected[0] === option.key ? 'border-accent bg-paper' : 'border-line bg-paper'
                }`}
              >
                <input
                  type="radio"
                  name="checkin-option"
                  className="mt-0.5"
                  checked={selected[0] === option.key}
                  onChange={() => choose(option.key)}
                />
                <span>
                  <span className="mr-1 text-muted-foreground">{index + 1}.</span>
                  {option.label}
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}

      {item.kind === 'mini_exercise' || item.kind === 'self_explain' ? (
        <textarea
          className="mt-3 w-full rounded-md border border-line bg-paper p-2 text-sm"
          rows={3}
          value={freeText}
          onChange={(event) => setFreeText(event.target.value)}
          placeholder="In your own words…"
          aria-label={item.prompt}
        />
      ) : null}

      {result ? (
        <p role="status" aria-live="polite" className="mt-3 flex items-center gap-2 text-sm">
          <CheckCircle2 aria-hidden="true" className="size-4 text-accent" />
          {result.result.feedback || 'Thanks — saved.'}
        </p>
      ) : null}

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={submit}
          disabled={!canSubmit || pending || result !== null}
          className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-paper disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {pending ? 'Saving…' : 'Submit'}
        </button>
        <button
          type="button"
          onClick={dismiss}
          disabled={pending}
          className="text-sm text-muted-foreground underline underline-offset-4"
        >
          Not now
        </button>
      </div>
    </motion.section>
  );
}

function likertValues(min: number, max: number): number[] {
  const values: number[] = [];
  for (let value = min; value <= max; value += 1) values.push(value);
  return values;
}

function gateNote(gate: string, retryAfter: number | null): string {
  if (gate === 'cooldown' && retryAfter) {
    const minutes = Math.max(1, Math.round(retryAfter / 60));
    return `Check-ins are on a short cooldown — next one in about ${minutes} min.`;
  }
  if (gate === 'quiz_active') return 'Finish the quiz first — no check-ins during a quiz.';
  if (gate === 'budget_exhausted') return 'You have used all check-ins for this session.';
  return '';
}
