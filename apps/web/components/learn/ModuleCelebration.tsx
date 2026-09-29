'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'motion/react';

/** Deterministic spark offsets — no randomness, so renders stay reproducible. */
const SPARKS = [
  { x: -72, y: -34 },
  { x: -44, y: -52 },
  { x: -18, y: -30 },
  { x: 12, y: -56 },
  { x: 38, y: -28 },
  { x: 66, y: -46 },
  { x: -58, y: 26 },
  { x: -26, y: 40 },
  { x: 8, y: 30 },
  { x: 44, y: 44 },
  { x: 70, y: 20 },
  { x: 0, y: -70 },
];

/**
 * Milestone celebration shown only when a module is finished. Motion is fully
 * skipped under `prefers-reduced-motion` (the message and link remain).
 */
export function ModuleCelebration({
  moduleTitle,
  hubHref,
}: {
  moduleTitle: string;
  hubHref: string;
}) {
  const reduced = useReducedMotion();

  return (
    <motion.section
      role="status"
      aria-live="polite"
      initial={reduced ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className="relative mt-8 border border-primary bg-accent p-6 text-center"
    >
      {reduced ? null : (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
          {SPARKS.map((spark, sparkIndex) => (
            <motion.span
              key={sparkIndex}
              initial={{ x: 0, y: 0, opacity: 1 }}
              animate={{ x: spark.x, y: spark.y, opacity: 0 }}
              transition={{ duration: 0.9, delay: sparkIndex * 0.03 }}
              className="absolute top-1/2 left-1/2 block size-1.5 rounded-full bg-primary"
            />
          ))}
        </div>
      )}
      <p className="text-lg font-semibold">Module complete!</p>
      <p className="mt-1 text-sm text-muted-foreground">You finished {moduleTitle}.</p>
      <Link href={hubHref} className="mt-4 inline-block underline underline-offset-4">
        Back to your learning path
      </Link>
    </motion.section>
  );
}
