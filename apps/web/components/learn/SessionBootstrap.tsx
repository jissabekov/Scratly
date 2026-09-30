'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { loadStoredSessionId } from '@/lib/session';
import { RouteBackLink } from '@/components/flow/RouteBackLink';

/**
 * Resolves the learning route to the stored student session.
 *
 * Session identity stays in localStorage (the existing `lib/session.ts`
 * pattern) — never in a shareable URL. If a session exists we replace the URL
 * with the *current* pathname plus `?session=<id>` so the server component can
 * fetch (preserving `/progress` and quiz routes); otherwise we explain how to
 * get here. Progress is never stored client-side.
 */
export function SessionBootstrap() {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const sessionId = loadStoredSessionId();
    if (sessionId) {
      router.replace(`${pathname}?session=${encodeURIComponent(sessionId)}`);
      return;
    }
    setChecked(true);
  }, [router, pathname]);

  return (
    <section className="mx-auto w-full max-w-3xl px-4 pb-10 pt-10">
      <h1 className="text-2xl font-semibold">Learning path</h1>
      <p className="mt-3 text-muted-foreground">
        {checked
          ? 'Start a chat first — your lessons appear here once we know who you are.'
          : 'Loading your learning path…'}
      </p>
      <p className="mt-4">
        <RouteBackLink href="/" label="Back to chat" />
      </p>
    </section>
  );
}
