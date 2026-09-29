'use server';

import { revalidatePath } from 'next/cache';
import { api } from './api';
import type { QuizAttemptResult, QuizItemCheck, SlideCompleteResult } from './types';

export type CompleteSlideInput = {
  sessionId: string;
  moduleId: string;
  slideId: string;
  requestId: string;
  timeOnSlideMs: number | null;
};

/**
 * Persist one slide completion through FastAPI (the only state authority).
 * The API is idempotent by request_id, so a retry with the same id is safe.
 */
export async function completeSlideAction(
  input: CompleteSlideInput
): Promise<SlideCompleteResult> {
  const result = await api<SlideCompleteResult>(
    `/v1/sessions/${input.sessionId}/learning/slides/${input.slideId}/complete`,
    {
      method: 'POST',
      body: JSON.stringify({
        request_id: input.requestId,
        time_on_slide_ms: input.timeOnSlideMs,
      }),
    }
  );
  revalidatePath('/modules');
  revalidatePath(`/modules/${input.moduleId}`);
  return result;
}

export type CheckQuizItemInput = {
  sessionId: string;
  attemptId: string;
  itemId: string;
  response: string[];
  latencyMs: number | null;
};

/**
 * Check one quiz answer and return immediate feedback. Answers stay on the
 * server: only the answered item's result and correct key come back.
 */
export async function checkQuizItemAction(input: CheckQuizItemInput): Promise<QuizItemCheck> {
  return api<QuizItemCheck>(
    `/v1/sessions/${input.sessionId}/learning/quiz-attempts/${input.attemptId}/responses`,
    {
      method: 'POST',
      body: JSON.stringify({
        item_id: input.itemId,
        response: input.response,
        latency_ms: input.latencyMs,
      }),
    }
  );
}

export type SubmitQuizAttemptInput = {
  sessionId: string;
  moduleId: string;
  attemptId: string;
  requestId: string;
  responses: { item_id: string; response: string[]; latency_ms: number | null }[];
};

/** Score a whole attempt. Idempotent by request_id. */
export async function submitQuizAttemptAction(
  input: SubmitQuizAttemptInput
): Promise<QuizAttemptResult> {
  const result = await api<QuizAttemptResult>(
    `/v1/sessions/${input.sessionId}/learning/quiz-attempts`,
    {
      method: 'POST',
      body: JSON.stringify({
        request_id: input.requestId,
        attempt_id: input.attemptId,
        responses: input.responses,
      }),
    }
  );
  // Deliberately no revalidatePath here: the learning pages are force-dynamic,
  // and refreshing the current route would replace the result screen with the
  // "quiz already passed" gate before the student could read it.
  return result;
}
