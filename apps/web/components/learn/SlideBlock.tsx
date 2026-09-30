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

/** Split plain text on blank lines into paragraphs. No HTML or markdown. */
function TextParagraphs({ text }: { text: string }) {
  const paragraphs = text.split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);
  if (paragraphs.length <= 1) {
    return <p className="min-w-0 break-words text-lg leading-relaxed">{text}</p>;
  }
  return (
    <div className="flex min-w-0 flex-col gap-3">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="min-w-0 break-words text-lg leading-relaxed">
          {paragraph}
        </p>
      ))}
    </div>
  );
}

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
      return <TextParagraphs text={block.text} />;
    case 'callout':
      return (
        <aside className={cn('min-w-0 border-l-4 p-4', CALLOUT_TONE[block.tone])}>
          {block.title ? <p className="font-semibold">{block.title}</p> : null}
          <p className="break-words text-base leading-relaxed">{block.text}</p>
        </aside>
      );
    case 'diagram':
      return (
        <figure className="border border-line bg-panel p-4" aria-label={block.alt}>
          {block.steps.length > 0 ? (
            <ol className="min-w-0 list-decimal space-y-1 pl-5 text-sm leading-relaxed">
              {block.steps.map((step, stepIndex) => (
                <li key={stepIndex} className="break-words">
                  {step}
                </li>
              ))}
            </ol>
          ) : null}
          {block.caption ? (
            <figcaption className="mt-2 break-words text-xs text-muted-foreground">
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
        <section className="min-w-0 border border-line bg-panel p-4">
          <h3 className="break-words font-semibold">{block.title}</h3>
          <ol className="mt-2 min-w-0 list-decimal space-y-1 pl-5 text-sm leading-relaxed">
            {block.steps.map((step, stepIndex) => (
              <li key={stepIndex} className="break-words">
                {step}
              </li>
            ))}
          </ol>
        </section>
      );
  }
}
