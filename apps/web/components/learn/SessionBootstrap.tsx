'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { loadStoredSessionId } from '@/lib/session';

/**
 * Resolves the learning route to the stored student session.
 *
 * Session identity stays in localStorage (the existing `lib/session.ts`
 * pattern) — never in a shareable URL. If a session exists we replace the URL
 * with `?session=<id>` so the server component can fetch; otherwise we explain
 * how to get here. Progress is never stored client-side.
 */
export function SessionBootstrap() {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const sessionId = loadStoredSessionId();
    if (sessionId) {
      router.replace(`/modules?session=${encodeURIComponent(sessionId)}`);
      return;
    }
    setChecked(true);
  }, [router]);

  return (
    <section className="mx-auto w-full max-w-3xl px-4 pb-32 pt-10">
      <h1 className="text-2xl font-semibold">Learning path</h1>
      <p className="mt-3 text-muted-foreground">
        {checked
          ? 'Start a chat first — your lessons appear here once we know who you are.'
          : 'Loading your learning path…'}
      </p>
      <p className="mt-4">
        <Link className="underline underline-offset-4" href="/">
          Go to the chat
        </Link>
      </p>
    </section>
  );
}
