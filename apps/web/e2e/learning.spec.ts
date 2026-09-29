import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { API, axeViolations, openLearningHub, seedSessionViaApi } from './helpers';

type Hub = {
  session_id: string;
  archetype_key: string;
  modules: {
    id: string;
    title: string;
    seq: number;
    state: string;
    quiz_gate_locked: boolean;
  }[];
  mastery_pct: number;
};

type CheckBlock = {
  type: 'check';
  answer_key: string;
  options: { key: string; label: string }[];
};

type Detail = {
  module: { id: string; title: string };
  slides: { id: string; completed: boolean; content: CheckBlock[] }[];
};

async function fetchHub(request: APIRequestContext, sessionId: string): Promise<Hub> {
  const response = await request.get(`${API}/v1/sessions/${sessionId}/learning`);
  expect(response.ok(), 'GET learning hub must succeed').toBeTruthy();
  return response.json();
}

async function fetchDetail(
  request: APIRequestContext,
  sessionId: string,
  moduleId: string
): Promise<Detail> {
  const response = await request.get(
    `${API}/v1/sessions/${sessionId}/learning/modules/${moduleId}`
  );
  expect(response.ok(), 'GET module detail must succeed').toBeTruthy();
  return response.json();
}

async function expectAxeClean(page: Page) {
  const violations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
  expect(
    violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
  ).toEqual([]);
}

test.describe('Learning hub and slide player', () => {
  test('hub resolves the stored session and shows the path with a locked quiz gate', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    expect(hub.modules.length).toBeGreaterThanOrEqual(2);
    expect(hub.modules[0].state).toBe('available');
    expect(hub.modules[1].state).toBe('locked');

    // Bootstrap resolves the localStorage session into the URL, then renders.
    await openLearningHub(page, sessionId);
    await expect(page.getByRole('heading', { name: 'Your learning path' })).toBeVisible({
      timeout: 30_000,
    });
    await expect.poll(() => new URL(page.url()).searchParams.get('session')).toBe(sessionId);

    // Exactly one active step is marked for assistive tech.
    await expect(page.locator('[aria-current="step"]')).toHaveCount(1);
    await expect(page.getByText('Quiz gate locked (Plan 04)').first()).toBeVisible();
    await expect(page.getByText('Locked').first()).toBeVisible();

    await expectAxeClean(page);
  });

  test('hub links into a module and the player is accessible', async ({ page, request }) => {
    const { sessionId } = await seedSessionViaApi(request);
    await openLearningHub(page, sessionId);
    await expect(page.getByRole('heading', { name: 'Your learning path' })).toBeVisible({
      timeout: 30_000,
    });

    await page.getByRole('link', { name: /Behind the Swipe/ }).click();
    await expect(page.getByText(/Step 1 of \d+/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('heading', { level: 2 })).toBeVisible();
    await expectAxeClean(page);
  });

  test('deep link, completion persistence, refresh, and Back all restore position', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    const moduleId = hub.modules[0].id;
    const detail = await fetchDetail(request, sessionId, moduleId);
    const total = detail.slides.length;
    expect(total).toBeGreaterThan(1);

    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key, value),
      ['scratly.student.session_id', sessionId]
    );
    // Deep-link straight to slide 1: no click path required.
    await page.goto(`/modules/${moduleId}?session=${sessionId}&slide=1`);
    await expect(page.getByText(`Step 1 of ${total}`)).toBeVisible({ timeout: 30_000 });

    // Complete slide 1 through the UI (slide 1 is a plain text slide).
    await page.getByRole('button', { name: 'Continue' }).click();
    await expect(page.getByText(`Step 2 of ${total}`)).toBeVisible({ timeout: 30_000 });
    expect(new URL(page.url()).searchParams.get('slide')).toBe('2');

    // The server — not the browser — owns progress.
    await expect
      .poll(
        async () => (await fetchDetail(request, sessionId, moduleId)).slides[0].completed,
        { timeout: 30_000 }
      )
      .toBe(true);

    // Browser Back returns to the previous slide (URL is the source of truth).
    await page.goBack();
    await expect
      .poll(() => new URL(page.url()).searchParams.get('slide'), { timeout: 30_000 })
      .toBe('1');
    await expect(page.getByText(`Step 1 of ${total}`)).toBeVisible({ timeout: 30_000 });

    // Refresh restores position from URL + server.
    await page.reload();
    await expect(page.getByText(`Step 1 of ${total}`)).toBeVisible({ timeout: 30_000 });

    await expectAxeClean(page);
  });

  test('an in-slide check never advances silently and retries after a wrong answer', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    const moduleId = hub.modules[0].id;
    const detail = await fetchDetail(request, sessionId, moduleId);

    const checkIndex = detail.slides.findIndex((slide) =>
      slide.content.some((block) => block.type === 'check')
    );
    expect(checkIndex, 'week-2 module must contain a check slide').toBeGreaterThanOrEqual(0);
    const check = detail.slides[checkIndex].content.find(
      (block): block is CheckBlock => block.type === 'check'
    )!;
    const wrong = check.options.find((option) => option.key !== check.answer_key)!;
    const right = check.options.find((option) => option.key === check.answer_key)!;

    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key, value),
      ['scratly.student.session_id', sessionId]
    );
    await page.goto(`/modules/${moduleId}?session=${sessionId}&slide=${checkIndex + 1}`);
    const primary = page.getByRole('button', { name: 'Continue' });
    await expect(primary).toBeDisabled();

    await page.getByRole('radio', { name: wrong.label }).check();
    await expect(page.getByText(/Not quite/)).toBeVisible();
    await expect(primary).toBeDisabled();

    await page.getByRole('radio', { name: right.label }).check();
    await expect(page.getByText(/^Correct\./)).toBeVisible();
    await expect(primary).toBeEnabled();

    await expectAxeClean(page);
  });
});
