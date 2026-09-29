'use client';

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { FlowActionBar } from '@/components/flow/FlowActionBar';
import { SlideProgress } from '@/components/flow/SlideProgress';
import { completeSlideAction } from '@/lib/actions';
import { newIdempotencyKey } from '@/lib/session';
import type { LearningModuleSummary, SlideItem } from '@/lib/types';
import { ModuleCelebration } from './ModuleCelebration';
import { SlideBlock } from './SlideBlock';

export type LessonPlayerProps = {
  sessionId: string;
  module: LearningModuleSummary;
  slides: SlideItem[];
  initialIndex: number;
};

const variants = {
  enter: (direction: number) => ({ x: direction > 0 ? 48 : -48, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({ x: direction > 0 ? -48 : 48, opacity: 0 }),
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

/**
 * Slide lesson player. Position lives in `?slide=` (deep-linkable, refresh- and
 * back-safe); every completion is written through a Server Action to FastAPI,
 * which is the only state authority — nothing is persisted in the browser.
 * Keyboard: ←/→ navigate, 1–4 pick options, Enter is the primary CTA.
 */
export function LessonPlayer({ sessionId, module, slides, initialIndex }: LessonPlayerProps) {
  const total = slides.length;
  const reduced = useReducedMotion();
  const hubHref = `/modules?session=${encodeURIComponent(sessionId)}`;

  const [index, setIndexState] = useState(() => clamp(initialIndex, 1, total));
  const [direction, setDirection] = useState(1);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [completed, setCompleted] = useState<Set<string>>(
    () => new Set(slides.filter((slide) => slide.completed).map((slide) => slide.id))
  );
  const [celebrating, setCelebrating] = useState(false);
  const [error, setError] = useState('');
  const [pending, startTransition] = useTransition();

  const headingRef = useRef<HTMLHeadingElement>(null);
  const enteredAtRef = useRef(Date.now());
  const indexRef = useRef(index);

  const slide = slides[clamp(index, 1, total) - 1];
  const isLast = index >= total;

  const checks = useMemo(() => {
    const found: { blockIndex: number; answerKey: string; selected?: string }[] = [];
    slide?.content.forEach((block, blockIndex) => {
      if (block.type === 'check') {
        found.push({
          blockIndex,
          answerKey: block.answer_key,
          selected: answers[`${slide.id}:${blockIndex}`],
        });
      }
    });
    return found;
  }, [slide, answers]);
  const allCorrect = checks.every((check) => check.selected === check.answerKey);

  // The URL is the source of truth for position. Next's router replaces (rather
  // than pushes) search-param-only navigations, which would break browser Back,
  // so slide changes use the native History API and a popstate listener.
  const updateUrl = useCallback((next: number) => {
    const url = new URL(window.location.href);
    url.searchParams.set('slide', String(next));
    window.history.pushState({ slide: next }, '', url);
  }, []);

  const goTo = useCallback(
    (next: number, dir: 1 | -1) => {
      const clamped = clamp(next, 1, total);
      setDirection(dir);
      setIndexState(clamped);
      updateUrl(clamped);
    },
    [total, updateUrl]
  );

  // Restore position on browser Back/Forward.
  useEffect(() => {
    const onPopState = () => {
      const raw = new URL(window.location.href).searchParams.get('slide');
      const parsed = raw ? Number.parseInt(raw, 10) : Number.NaN;
      if (!Number.isFinite(parsed)) return;
      const next = clamp(parsed, 1, total);
      setDirection(next > indexRef.current ? 1 : -1);
      setIndexState(next);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, [total]);

  // Focus the step heading and restart the time-on-slide clock on transition.
  useEffect(() => {
    indexRef.current = index;
    enteredAtRef.current = Date.now();
    headingRef.current?.focus();
  }, [index]);

  const handleSelect = useCallback(
    (blockIndex: number, key: string) => {
      setAnswers((prev) => ({ ...prev, [`${slide.id}:${blockIndex}`]: key }));
    },
    [slide.id]
  );

  const selectOption = useCallback(
    (optionIndex: number) => {
      const entry = slide.content.findIndex((block) => block.type === 'check');
      if (entry < 0) return;
      const block = slide.content[entry];
      if (block.type !== 'check') return;
      const option = block.options[optionIndex];
      if (option) handleSelect(entry, option.key);
    },
    [slide, handleSelect]
  );

  const advance = useCallback(() => {
    if (!allCorrect || pending) return;
    const target = index;
    startTransition(async () => {
      try {
        if (!completed.has(slide.id)) {
          await completeSlideAction({
            sessionId,
            moduleId: module.id,
            slideId: slide.id,
            requestId: newIdempotencyKey(),
            timeOnSlideMs: Date.now() - enteredAtRef.current,
          });
          setCompleted((prev) => new Set(prev).add(slide.id));
        }
        if (isLast) setCelebrating(true);
        else goTo(target + 1, 1);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }, [allCorrect, pending, index, completed, slide.id, sessionId, module.id, isLast, goTo]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target !== null && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA');
      if (typing) {
        // Native radios keep their own arrow behaviour; Enter still advances.
        if (event.key === 'Enter') {
          event.preventDefault();
          advance();
        }
        return;
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        advance();
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        if (index > 1) goTo(index - 1, -1);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        advance();
      } else if (/^[1-4]$/.test(event.key)) {
        event.preventDefault();
        selectOption(Number(event.key) - 1);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [advance, goTo, index, selectOption]);

  if (total === 0) {
    return (
      <main className="mx-auto w-full max-w-3xl px-4 pt-10">
        <h1 className="text-2xl font-semibold">{module.title}</h1>
        <p className="mt-3 text-muted-foreground">This module has no slides yet.</p>
        <p className="mt-4">
          <Link className="underline underline-offset-4" href={hubHref}>
            Back to your learning path
          </Link>
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-28 pt-6">
      <div className="mb-4 flex items-center gap-3">
        <Link
          href={hubHref}
          className="shrink-0 text-sm text-muted-foreground underline underline-offset-4"
        >
          ← Learning path
        </Link>
        <div className="flex-1">
          <SlideProgress current={index} total={total} />
        </div>
      </div>

      <p className="text-xs tracking-wide text-muted-foreground uppercase">
        {module.title} · {slide.lesson_title}
      </p>
      <h2
        ref={headingRef}
        tabIndex={-1}
        className="mt-1 text-xl font-semibold outline-none"
      >
        {slide.title || `Slide ${index}`}
      </h2>

      <div className="relative mt-5 min-h-64">
        <AnimatePresence mode="wait" custom={direction} initial={false}>
          <motion.div
            key={slide.id}
            custom={direction}
            variants={reduced ? undefined : variants}
            initial={reduced ? false : 'enter'}
            animate={reduced ? undefined : 'center'}
            exit={reduced ? undefined : 'exit'}
            transition={{ duration: reduced ? 0 : 0.22 }}
            className="flex flex-col gap-4"
          >
            {slide.content.map((block, blockIndex) => (
              <SlideBlock
                key={blockIndex}
                block={block}
                slideId={slide.id}
                blockIndex={blockIndex}
                selectedKey={answers[`${slide.id}:${blockIndex}`]}
                onSelect={(key) => handleSelect(blockIndex, key)}
              />
            ))}
          </motion.div>
        </AnimatePresence>
      </div>

      {error ? (
        <p role="alert" className="mt-4 text-sm text-warn">
          {error}
        </p>
      ) : null}
      {celebrating ? <ModuleCelebration moduleTitle={module.title} hubHref={hubHref} /> : null}

      <FlowActionBar
        onBack={index > 1 ? () => goTo(index - 1, -1) : undefined}
        backLabel="Back"
        primaryLabel={celebrating ? 'Module complete' : isLast ? 'Finish module' : 'Continue'}
        onPrimary={advance}
        primaryDisabled={!allCorrect || celebrating}
        pending={pending}
      />
    </main>
  );
}
