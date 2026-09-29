import { expect, type Page, type APIRequestContext } from '@playwright/test';

export const API = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
export const SESSION_KEY = 'scratly.student.session_id';

/** Create a session directly through the API (seeded-session convention). */
export async function seedSessionViaApi(
  request: APIRequestContext
): Promise<{ sessionId: string; stage: string }> {
  const response = await request.post(`${API}/v1/sessions`);
  expect(response.ok(), 'POST /v1/sessions must succeed').toBeTruthy();
  const body = await response.json();
  return { sessionId: body.session_id, stage: body.stage };
}

/**
 * Open the chat with a pre-seeded session id in localStorage
 * (addInitScript runs before any page script, so hydration picks it up).
 */
export async function openSeededSession(page: Page, sessionId: string): Promise<void> {
  await page.addInitScript(
    ([key, value]) => {
      window.localStorage.setItem(key, value);
    },
    [SESSION_KEY, sessionId]
  );
  await page.goto('/');
}

/** Run axe against the current page state and return violations. */
export async function axeViolations(page: Page, tag?: string) {
  const { AxeBuilder } = await import('@axe-core/playwright');
  const builder = new AxeBuilder({ page });
  if (tag) builder.withTags([tag]);
  const { violations } = await builder.analyze();
  return violations;
}
