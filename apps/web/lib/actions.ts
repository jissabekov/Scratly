'use server';

import { revalidatePath } from 'next/cache';
import { api } from './api';
import type { SlideCompleteResult } from './types';

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
