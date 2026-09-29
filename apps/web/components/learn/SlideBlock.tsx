import { cn } from '@/lib/utils';
import { CheckBlock } from './CheckBlock';
import type { SlideBlock as SlideBlockType } from '@/lib/types';

const CALLOUT_TONE: Record<'info' | 'success' | 'warning', string> = {
  info: 'border-info bg-info-tint',
  success: 'border-success bg-success-tint',
  warning: 'border-warning bg-warning-tint',
};

export type SlideBlockProps = {
  block: SlideBlockType;
  slideId: string;
  blockIndex: number;
  selectedKey?: string;
  onSelect: (key: string) => void;
};

/** The single renderer for typed content blocks — never free-form HTML. */
export function SlideBlock({
  block,
  slideId,
  blockIndex,
  selectedKey,
  onSelect,
}: SlideBlockProps) {
  switch (block.type) {
    case 'text':
      return <p className="text-lg leading-relaxed">{block.text}</p>;
    case 'callout':
      return (
        <aside className={cn('border-l-4 p-4', CALLOUT_TONE[block.tone])}>
          {block.title ? <p className="font-semibold">{block.title}</p> : null}
          <p className="text-base">{block.text}</p>
        </aside>
      );
    case 'diagram':
      return (
        <figure className="border border-line bg-panel p-4">
          <div
            role="img"
            aria-label={block.alt}
            className="flex items-center justify-center border border-dashed border-line bg-accent p-6 text-xs tracking-wide text-muted-foreground uppercase"
          >
            {block.asset}
          </div>
          {block.steps.length > 0 ? (
            <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
              {block.steps.map((step, stepIndex) => (
                <li key={stepIndex}>{step}</li>
              ))}
            </ol>
          ) : null}
          {block.caption ? (
            <figcaption className="mt-2 text-xs text-muted-foreground">
              {block.caption}
            </figcaption>
          ) : null}
        </figure>
      );
    case 'check':
      return (
        <CheckBlock
          block={block}
          selectedKey={selectedKey}
          onSelect={onSelect}
          groupName={`${slideId}-${blockIndex}`}
        />
      );
    case 'worked_example':
      return (
        <section className="border border-line bg-panel p-4">
          <h3 className="font-semibold">{block.title}</h3>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {block.steps.map((step, stepIndex) => (
              <li key={stepIndex}>{step}</li>
            ))}
          </ol>
        </section>
      );
  }
}
