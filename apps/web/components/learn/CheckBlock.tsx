'use client';

import { cn } from '@/lib/utils';
import type { SlideBlock } from '@/lib/types';

export type CheckBlockProps = {
  block: Extract<SlideBlock, { type: 'check' }>;
  selectedKey: string | undefined;
  onSelect: (key: string) => void;
  groupName: string;
};

/**
 * A retryable, low-stakes in-slide check. Feedback (and the explanation) shows
 * immediately on selection and is announced politely; a wrong answer never
 * advances silently. Native radios inside a fieldset/legend keep the whole row
 * clickable and the control fully keyboard-operable.
 */
export function CheckBlock({ block, selectedKey, onSelect, groupName }: CheckBlockProps) {
  const answered = selectedKey !== undefined;
  const correct = selectedKey === block.answer_key;

  return (
    <div className="border border-line bg-panel p-4">
      <fieldset>
        <legend className="text-sm font-semibold">{block.question}</legend>
        <div className="mt-3 flex flex-col gap-2">
          {block.options.map((option) => {
            const isSelected = selectedKey === option.key;
            const showRight = isSelected && correct;
            const showWrong = isSelected && !correct;
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
                  type="radio"
                  name={groupName}
                  value={option.key}
                  checked={isSelected}
                  onChange={() => onSelect(option.key)}
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
        className={cn('mt-3 text-sm', correct ? 'text-success' : 'text-warn')}
      >
        {answered ? (correct ? `Correct. ${block.explanation}` : `Not quite. ${block.explanation}`) : ''}
      </p>
    </div>
  );
}
