import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type RouteBackLinkProps = {
  href: string;
  /** Visible label and accessible name, e.g. "Back to chat". */
  label: string;
  className?: string;
};

/**
 * Route-level Back control (Plan 08 W8.2): shadcn ghost Button via asChild +
 * next/link so it is a real `<a>` (middle-click / open-in-new-tab) and a
 * visible button. Minimum hit height 44px.
 */
export function RouteBackLink({ href, label, className }: RouteBackLinkProps) {
  return (
    <Button asChild variant="ghost" className={cn('min-h-11 px-3', className)}>
      <Link href={href}>{label}</Link>
    </Button>
  );
}
