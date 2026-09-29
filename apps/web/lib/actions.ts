'use server';

import { revalidatePath } from 'next/cache';
import { api } from './api';
import type {
  CheckinDeliver,
  CheckinDismissResult,
  CheckinResult,
  QuizAttemptResult,
  QuizItemCheck,
  SlideCompleteResult,
} from './types';

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

export type DeliverCheckinInput = { sessionId: string };

/** Ask the deterministic scheduler for the next check-in (or a gate reason). */
export async function deliverCheckinAction(
  input: DeliverCheckinInput
): Promise<CheckinDeliver> {
  return api<CheckinDeliver>(`/v1/sessions/${input.sessionId}/learning/checkins`);
}

export type RespondCheckinInput = {
  sessionId: string;
  checkinId: string;
  requestId: string;
  response: string[];
  freeText: string;
  latencyMs: number | null;
};

/** Score one check-in response. Idempotent by request_id. */
export async function respondCheckinAction(
  input: RespondCheckinInput
): Promise<CheckinResult> {
  return api<CheckinResult>(
    `/v1/sessions/${input.sessionId}/learning/checkins/${input.checkinId}`,
    {
      method: 'POST',
      body: JSON.stringify({
        request_id: input.requestId,
        response: input.response,
        free_text: input.freeText,
        latency_ms: input.latencyMs,
      }),
    }
  );
}

export type DismissCheckinInput = {
  sessionId: string;
  checkinId: string;
  requestId: string;
  reason?: string;
};

/** Dismiss ("not now"). The API doubles the cooldown. */
export async function dismissCheckinAction(
  input: DismissCheckinInput
): Promise<CheckinDismissResult> {
  return api<CheckinDismissResult>(
    `/v1/sessions/${input.sessionId}/learning/checkins/${input.checkinId}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ request_id: input.requestId, reason: input.reason ?? '' }),
    }
  );
}
