import type { ObjectiveMastery } from '@/lib/types';

const STATE_LABEL: Record<string, string> = {
  unseen: 'Not started',
  learning: 'Learning',
  mastered: 'Mastered',
  decaying: 'Needs review',
};

const STATE_CLASS: Record<string, string> = {
  unseen: 'border-line bg-paper text-muted-foreground',
  learning: 'border-line bg-panel',
  mastered: 'border-accent bg-accent text-paper',
  decaying: 'border-warn bg-panel text-warn',
};

export type MasteryGridProps = {
  mastery: ObjectiveMastery[];
  className?: string;
};

/**
 * Khan-style mastery grid (Plan 05 W5.4). Pure presentational server component:
 * `decaying` objectives are shown in the warn token, never as a re-lock.
 */
export function MasteryGrid({ mastery, className }: MasteryGridProps) {
  if (mastery.length === 0) {
    return (
      <p className="mt-2 text-sm text-muted-foreground">
        Finish a module to start building mastery here.
      </p>
    );
  }
  return (
    <ul
      className={`mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 ${className ?? ''}`}
      aria-label="Mastery by objective"
    >
      {mastery.map((objective) => {
        const state = objective.state in STATE_LABEL ? objective.state : 'learning';
        return (
          <li
            key={objective.objective_code}
            className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm ${STATE_CLASS[state]}`}
          >
            <span className="pr-2">{objective.objective_code.replace(/_/g, ' ')}</span>
            <span className="shrink-0 text-xs uppercase tracking-wide">
              {STATE_LABEL[state]}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
