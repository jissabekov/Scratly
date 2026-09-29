/**
 * Phase 4 quiz gating e2e.
 *
 * PRECONDITION: the API must run with `LEARNING_QUIZ_COOLDOWN_SECONDS=0`
 * (the default 600s cooldown is by design and would otherwise block the
 * immediate retry the remediation loop promises). The first test asserts the
 * precondition explicitly rather than weakening any assertion.
 */
import { randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { API, axeViolations, seedSessionViaApi } from './helpers';

/** request_id is globally unique on quiz attempts — never reuse a literal. */
const requestId = (label: string) => `${label}-${randomUUID()}`;

type Item = { id: string; kind: string; options: { key: string; label: string }[] };
type Draw = {
  gate: string;
  attempts_used: number;
  max_attempts: number;
  retry_after_seconds: number | null;
  attempt: { attempt_id: string; attempt_no: number; form_id: number; items: Item[] } | null;
};
type Hub = { modules: { id: string; seq: number; state: string }[] };

async function fetchHub(request: APIRequestContext, sessionId: string): Promise<Hub> {
  const response = await request.get(`${API}/v1/sessions/${sessionId}/learning`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function fetchDraw(
  request: APIRequestContext,
  sessionId: string,
  moduleId: string
): Promise<Draw> {
  const response = await request.get(
    `${API}/v1/sessions/${sessionId}/learning/modules/${moduleId}/quiz`
  );
  expect(response.ok(), 'GET quiz draw must succeed').toBeTruthy();
  return response.json();
}

/** Learn each item's correct keys by checking an empty answer (server-side). */
async function correctKeys(
  request: APIRequestContext,
  sessionId: string,
  draw: Draw
): Promise<Map<string, string[]>> {
  const answers = new Map<string, string[]>();
  for (const item of draw.attempt!.items) {
    const response = await request.post(
      `${API}/v1/sessions/${sessionId}/learning/quiz-attempts/${draw.attempt!.attempt_id}/responses`,
      { data: { item_id: item.id, response: [] } }
    );
    expect(response.ok(), 'POST item check must succeed').toBeTruthy();
    const body = await response.json();
    answers.set(item.id, body.correct_answer as string[]);
  }
  return answers;
}

function wrongKeys(item: Item, correct: string[]): string[] {
  const candidate = item.options.find((option) => !correct.includes(option.key));
  return candidate ? [candidate.key] : [];
}

async function answerCurrent(page: Page, item: Item, keys: string[]): Promise<void> {
  expect(keys.length, `no answer keys available for item ${item.id}`).toBeGreaterThan(0);
  // Scope to the live question block: the previous one is still animating out.
  const scope = page.getByTestId('quiz-question');
  if (item.kind === 'select_all') {
    for (const key of keys) {
      const box = scope.locator(`input[type="checkbox"][value="${key}"]`);
      await box.check();
      await expect(box).toBeChecked();
    }
    await page.getByRole('button', { name: 'Check answer' }).click();
  } else {
    const radio = scope.locator(`input[type="radio"][value="${keys[0]}"]`);
    await radio.check();
    await expect(radio).toBeChecked();
  }
  // The CTA only flips to Next/See results once the server-side check settled.
  // Waiting on it (rather than on feedback text) avoids matching a stale
  // element that is still animating out from the previous question.
  await expect(page.getByRole('button', { name: /^(Next|See results)$/ })).toBeEnabled({
    timeout: 30_000,
  });
}

/** The step heading is unique (the live region repeats the same text). */
function questionHeading(page: Page, number: number, total: number) {
  return page.getByRole('heading', { name: `Question ${number} of ${total}` });
}

/**
 * The heading updates instantly, but the question block animates out/in, so we
 * must wait for the *stem* of the question we are about to answer — otherwise
 * a click can land on the question that is still animating away.
 */
async function awaitCurrentStem(page: Page, item: Item): Promise<void> {
  await expect(page.getByTestId('quiz-question').locator('legend')).toHaveText(item.stem, {
    timeout: 30_000,
  });
}

async function answerAll(page: Page, items: Item[], pick: (item: Item) => string[]): Promise<void> {
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    await awaitCurrentStem(page, item);
    await answerCurrent(page, item, pick(item));
    const last = index === items.length - 1;
    await page.getByRole('button', { name: last ? 'See results' : 'Next' }).click();
  }
}

async function expectAxeClean(page: Page) {
  const violations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
  expect(
    violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
  ).toEqual([]);
}

test.describe('Module quiz gating', () => {
  test('fail shows remediation, the alternate form passes, and the next module unlocks', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    const moduleId = hub.modules[0].id;

    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key, value),
      ['scratly.student.session_id', sessionId]
    );

    // --- attempt 1: answer everything wrong -------------------------------
    const first = await fetchDraw(request, sessionId, moduleId);
    expect(first.gate).toBe('available');
    expect(first.attempt!.items).toHaveLength(5);
    expect(first.attempt!.form_id).toBe(1);
    const firstAnswers = await correctKeys(request, sessionId, first);

    await page.goto(`/modules/${moduleId}/quiz?session=${sessionId}`);
    await expect(questionHeading(page, 1, 5)).toBeVisible({ timeout: 30_000 });
    // The step counter is announced politely for screen readers.
    await expect(page.getByRole('status').filter({ hasText: 'Question 1 of 5' })).toBeVisible();
    await answerAll(page, first.attempt!.items, (item) =>
      wrongKeys(item, firstAnswers.get(item.id) ?? [])
    );

    await expect(page.getByText(/not passed yet/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Worth another look')).toBeVisible();
    await expect(page.getByRole('link', { name: /Review slide \d+/ }).first()).toBeVisible();
    await expect(page.getByText('Re-teach before you retry')).toBeVisible();

    // Precondition: no cooldown, so the retry is offered immediately.
    const afterFail = await fetchDraw(request, sessionId, moduleId);
    expect(
      afterFail.gate,
      'quiz e2e requires the API to run with LEARNING_QUIZ_COOLDOWN_SECONDS=0'
    ).toBe('available');
    expect(afterFail.attempt!.attempt_no).toBe(2);
    expect(afterFail.attempt!.form_id).toBe(2);

    // --- attempt 2: alternate form, answer everything right ----------------
    const secondAnswers = await correctKeys(request, sessionId, afterFail);
    await page.goto(`/modules/${moduleId}/quiz?session=${sessionId}`);
    await expect(questionHeading(page, 1, 5)).toBeVisible({ timeout: 30_000 });
    await answerAll(page, afterFail.attempt!.items, (item) =>
      secondAnswers.get(item.id) ?? []
    );

    await expect(page.getByText(/Quiz passed/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('link', { name: 'Start the next module' })).toBeVisible();

    // Server state — not the DOM — decides the unlock.
    const afterPass = await fetchHub(request, sessionId);
    expect(afterPass.modules[0].state).toBe('passed');
    expect(afterPass.modules[1].state).toBe('available');
    await expectAxeClean(page);
  });

  test('three failed attempts end in a handoff card instead of a dead end', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    const moduleId = hub.modules[0].id;

    // Attempts 1 and 2 fail through the API (the UI path is covered above).
    for (const attempt of [1, 2]) {
      const draw = await fetchDraw(request, sessionId, moduleId);
      expect(draw.gate).toBe('available');
      expect(draw.attempt!.attempt_no).toBe(attempt);
      const answers = await correctKeys(request, sessionId, draw);
      const responses = draw.attempt!.items.map((item) => ({
        item_id: item.id,
        response: wrongKeys(item, answers.get(item.id) ?? []),
        latency_ms: 900,
      }));
      const submitted = await request.post(
        `${API}/v1/sessions/${sessionId}/learning/quiz-attempts`,
        {
          data: {
            request_id: requestId(`cap-attempt-${attempt}`),
            attempt_id: draw.attempt!.attempt_id,
            responses,
          },
        }
      );
      expect(submitted.ok()).toBeTruthy();
      const result = await submitted.json();
      expect(result.passed).toBe(false);
    }

    // Attempt 3 through the UI → handoff.
    const third = await fetchDraw(request, sessionId, moduleId);
    expect(third.attempt!.attempt_no).toBe(3);
    const thirdAnswers = await correctKeys(request, sessionId, third);

    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key, value),
      ['scratly.student.session_id', sessionId]
    );
    await page.goto(`/modules/${moduleId}/quiz?session=${sessionId}`);
    await expect(questionHeading(page, 1, 5)).toBeVisible({ timeout: 30_000 });
    await answerAll(page, third.attempt!.items, (item) =>
      wrongKeys(item, thirdAnswers.get(item.id) ?? [])
    );

    await expect(page.getByText(/not passed yet/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Handoff card created/)).toBeVisible();
    await expect(page.getByText(/good moment to talk it through/)).toBeVisible();

    // The gate is closed: no fourth attempt, module stays locked behind it.
    const afterCap = await fetchDraw(request, sessionId, moduleId);
    expect(afterCap.gate).toBe('handoff');
    expect(afterCap.attempts_used).toBe(3);
    expect(afterCap.attempt).toBeNull();
    const hubAfter = await fetchHub(request, sessionId);
    expect(hubAfter.modules[0].state).not.toBe('passed');
    expect(hubAfter.modules[1].state).toBe('locked');

    await page.goto(`/modules/${moduleId}/quiz?session=${sessionId}`);
    await expect(page.getByRole('heading', { name: /get some help/ })).toBeVisible();
    await expectAxeClean(page);
  });
});
