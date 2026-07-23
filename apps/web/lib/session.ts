const SESSION_KEY = 'scratly.student.session_id';

export function loadStoredSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function storeSessionId(sessionId: string): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(SESSION_KEY, sessionId);
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearStoredSessionId(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

/** Stable idempotency key for one send attempt (retry with same key). */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `turn-${crypto.randomUUID()}`;
  }
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export const STAGE_LABELS: Record<string, string> = {
  discovery: 'Discovery',
  measurement: 'Digging in',
  gap_resolution: 'Clearing up',
  profile_review: 'Review',
  project_matching: 'Matching',
  complete: 'Done',
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] || stage;
}
