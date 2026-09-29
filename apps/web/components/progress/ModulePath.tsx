import Link from 'next/link';
import { Check, Lock } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import type { LearningHub, LearningModuleState } from '@/lib/types';

const STATE_LABEL: Record<LearningModuleState, string> = {
  locked: 'Locked',
  available: 'Start',
  in_progress: 'In progress',
  passed: 'Passed',
};

function moduleHref(moduleId: string, sessionId: string, nextSlide: number): string {
  return `/modules/${moduleId}?session=${encodeURIComponent(sessionId)}&slide=${nextSlide}`;
}

/**
 * Duolingo-style module path. The active node carries `aria-current="step"`;
 * locked nodes are non-interactive and announce their quiz gate. The gate
 * itself stays locked until the Plan-04 quiz pass rule lands.
 */
export function ModulePath({ hub, sessionId }: { hub: LearningHub; sessionId: string }) {
  return (
    <ol className="mt-4 flex flex-col gap-3">
      {hub.modules.map((module) => {
        const locked = module.state === 'locked';
        const active = module.state === 'available' || module.state === 'in_progress';
        const nextSlide = Math.min(
          module.slides_completed + 1,
          Math.max(1, module.slides_total)
        );
        // All slides done but the gate is still closed → the node leads to the quiz.
        const quizReady =
          !locked &&
          module.quiz_gate_locked &&
          module.slides_total > 0 &&
          module.slides_completed >= module.slides_total;
        const href = quizReady
          ? `/modules/${module.id}/quiz?session=${encodeURIComponent(sessionId)}`
          : moduleHref(module.id, sessionId, nextSlide);

        const body = (
          <>
            <span
              aria-hidden="true"
              className={cn(
                'flex size-10 shrink-0 items-center justify-center rounded-full border text-sm font-semibold tabular-nums',
                locked
                  ? 'border-line text-muted-foreground'
                  : 'border-primary bg-accent text-ink'
              )}
            >
              {module.state === 'passed' ? <Check className="size-5" /> : module.seq}
            </span>
            <span className="flex min-w-0 flex-1 flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{module.title}</span>
                <span
                  className={cn(
                    'inline-flex items-center gap-1 border px-1.5 py-0.5 text-xs',
                    locked ? 'border-line text-muted-foreground' : 'border-primary text-ink'
                  )}
                >
                  {locked ? <Lock className="size-3" aria-hidden="true" /> : null}
                  {STATE_LABEL[module.state]}
                </span>
              </span>
              {module.description ? (
                <span className="text-sm text-muted-foreground">{module.description}</span>
              ) : null}
              <span className="text-xs text-muted-foreground">
                {module.est_minutes} min · {module.slides_completed}/{module.slides_total} slides
              </span>
              {module.state === 'in_progress' ? (
                <Progress
                  value={module.progress_pct}
                  aria-label={`${module.title} progress`}
                  className="mt-1 h-1.5"
                />
              ) : null}
              {quizReady ? (
                <span className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-ink">
                  Quiz ready — pass it to unlock the next module
                </span>
              ) : module.quiz_gate_locked ? (
                <span className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Lock className="size-3" aria-hidden="true" />
                  Quiz gate locked
                </span>
              ) : null}
            </span>
          </>
        );

        return (
          <li
            key={module.id}
            aria-current={active ? 'step' : undefined}
            className="list-none"
          >
            {locked ? (
              <div
                aria-disabled="true"
                className="flex items-start gap-3 border border-line bg-panel/60 p-4 opacity-70"
              >
                {body}
              </div>
            ) : (
              <Link
                href={href}
                className="flex items-start gap-3 border border-line bg-panel p-4 transition-colors hover:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {body}
              </Link>
            )}
          </li>
        );
      })}
    </ol>
  );
}
