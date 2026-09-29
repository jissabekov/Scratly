import { Suspense } from 'react';
import { notFound } from 'next/navigation';
import { api } from '../../../lib/api';
import type { ModuleDetail } from '../../../lib/types';
import { LessonPlayer } from '../../../components/learn/LessonPlayer';
import { SessionBootstrap } from '../../../components/learn/SessionBootstrap';

export const dynamic = 'force-dynamic';

/**
 * Module detail (server component) → LessonPlayer (client). Slide position is
 * read from `?slide=` so refresh, back, and deep links all restore in place.
 */
export default async function ModulePage({
  params,
  searchParams,
}: {
  params: Promise<{ moduleId: string }>;
  searchParams: Promise<{ session?: string; slide?: string }>;
}) {
  const { moduleId } = await params;
  const { session, slide } = await searchParams;
  if (!session) {
    return <SessionBootstrap />;
  }

  let detail: ModuleDetail | null = null;
  try {
    detail = await api<ModuleDetail>(
      `/v1/sessions/${encodeURIComponent(session)}/learning/modules/${encodeURIComponent(moduleId)}`
    );
  } catch {
    detail = null;
  }
  if (detail === null) {
    notFound();
  }

  const total = detail.slides.length;
  const requested = slide ? Number.parseInt(slide, 10) : Number.NaN;
  const initialIndex =
    Number.isFinite(requested) && requested >= 1
      ? Math.min(requested, Math.max(1, total))
      : Math.min(detail.progress.current_slide_index, Math.max(1, total));

  return (
    <Suspense fallback={null}>
      <LessonPlayer
        sessionId={session}
        module={detail.module}
        slides={detail.slides}
        initialIndex={initialIndex}
        quizHref={
          detail.quiz.available
            ? `/modules/${encodeURIComponent(moduleId)}/quiz?session=${encodeURIComponent(session)}`
            : null
        }
      />
    </Suspense>
  );
}
