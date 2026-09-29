"use client";

import * as React from "react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export type SlideProgressProps = {
  /** 1-based step number. */
  current: number;
  total: number;
  /** Announced/visible counter text; defaults to "Step x of n". */
  label?: string;
  className?: string;
};

/**
 * Slide progress bar (Plan 02 W2.4). Renders the Radix progressbar with
 * "Step x of n" announced politely by screen readers; the visible counter
 * doubles as the live region so refreshes are announced without a
 * duplicate hidden node.
 */
export function SlideProgress({ current, total, label, className }: SlideProgressProps) {
  const safeTotal = Math.max(0, total);
  const clamped = Math.min(safeTotal, Math.max(1, current));
  const pct = safeTotal > 0 ? Math.round((clamped / safeTotal) * 100) : 0;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <Progress value={pct} className="flex-1" aria-label={label ?? "Lesson progress"} />
      <span
        role="status"
        aria-live="polite"
        className="text-xs tabular-nums text-muted-foreground"
      >
        {safeTotal > 0 ? (label ?? `Step ${clamped} of ${safeTotal}`) : "No steps yet"}
      </span>
    </div>
  );
}
