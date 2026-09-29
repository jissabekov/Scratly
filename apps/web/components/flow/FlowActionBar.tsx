"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type FlowActionBarProps = {
  onBack?: () => void;
  backLabel?: string;
  primaryLabel: string;
  onPrimary: () => void;
  primaryDisabled?: boolean;
  pending?: boolean;
  className?: string;
  /** Extra actions rendered between the Back button and the primary CTA. */
  children?: React.ReactNode;
};

/**
 * Fixed bottom action bar shared by slide players and quizzes (Plan 02 W2.4).
 * Back is the ghost variant; the primary CTA is the committed next action.
 * Non-interactive states are announced via aria-busy for screen readers.
 */
export function FlowActionBar({
  onBack,
  backLabel = "Back",
  primaryLabel,
  onPrimary,
  primaryDisabled = false,
  pending = false,
  className,
  children,
}: FlowActionBarProps) {
  return (
    <div
      aria-busy={pending || undefined}
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 border-t border-line bg-paper/95 backdrop-blur supports-[backdrop-filter]:bg-paper/80",
        className
      )}
    >
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3">
        {onBack ? (
          <Button type="button" variant="ghost" onClick={onBack} disabled={pending}>
            {backLabel}
          </Button>
        ) : (
          <span aria-hidden="true" className="w-16 shrink-0" />
        )}
        <div className="flex-1" />
        {children}
        <Button type="button" onClick={onPrimary} disabled={primaryDisabled || pending}>
          {pending ? "Working…" : primaryLabel}
        </Button>
      </div>
    </div>
  );
}
