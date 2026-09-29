import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { API, axeViolations, openLearningHub, seedSessionViaApi } from './helpers';

type Hub = {
  session_id: string;
  modules: { id: string; title: string; state: string }[];
};

type CheckBlock = {
  type: 'check';
  answer_key: string;
  options: { key: string; label: string }[];
};

type Slide = {
  id: string;
  index: number;
  lesson_seq: number;
  completed: boolean;
  content: CheckBlock[];
};

type Detail = {
  module: { id: string; title: string };
  slides: Slide[];
  quiz: { available: boolean };
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

/** Index of the last slide of the first lesson (a section boundary). */
function firstSectionEnd(detail: Detail): number {
  const first = detail.slides[0]?.lesson_seq;
  let last = 0;
  for (const slide of detail.slides) {
    if (slide.lesson_seq !== first) break;
    last = slide.index;
  }
  return last;
}

async function answerChecks(page: Page, detail: Detail, index: number) {
  const slide = detail.slides.find((s) => s.index === index);
  for (const block of slide?.content ?? []) {
    if (block.type !== 'check') continue;
    const option = block.options.find((o) => o.key === block.answer_key);
    if (option) {
      await page.getByRole('radio', { name: option.label, exact: false }).first().click();
    }
  }
}

test.describe('Progress check-ins', () => {
  test('a section boundary delivers a dismissible check-in, and the dashboard renders', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    const module = hub.modules[0];
    const detail = await fetchDetail(request, sessionId, module.id);
    const boundary = firstSectionEnd(detail);
    expect(boundary, 'the first module must have a multi-slide lesson').toBeGreaterThan(0);

    await page.addInitScript(
      ([key, value]) => window.localStorage.setItem(key, value as string),
      ['scratly.student.session_id', sessionId]
    );
    await page.goto(`/modules/${module.id}?session=${sessionId}&slide=${boundary}`);
    await expect(page.getByRole('heading', { level: 2 })).toBeVisible({ timeout: 30_000 });
    await answerChecks(page, detail, boundary);

    await page.getByRole('button', { name: /continue/i }).click();

    // The widget is non-modal: the lesson keeps working around it.
    const widget = page.getByRole('region').filter({ has: page.getByText(/quick check-in/i) });
    await expect(widget).toBeVisible({ timeout: 30_000 });

    // Dismissing closes it without leaving the lesson.
    await widget.getByRole('button', { name: 'Not now' }).click();
    await expect(widget).toBeHidden({ timeout: 15_000 });

    // The dashboard reads the same session from the API.
    await page.goto(`/progress?session=${sessionId}`);
    await expect(page.getByRole('heading', { name: 'Progress', level: 1 })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/step streak/i)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Mastery by objective' })).toBeVisible();
    await expectAxeClean(page);
  });

  test('no check-in is delivered while a quiz attempt is open', async ({ request }) => {
    const { sessionId } = await seedSessionViaApi(request);
    const hub = await fetchHub(request, sessionId);
    const module = hub.modules[0];
    const detail = await fetchDetail(request, sessionId, module.id);
    expect(detail.quiz.available, 'first module quiz must be reachable').toBeTruthy();

    const draw = await request.get(
      `${API}/v1/sessions/${sessionId}/learning/modules/${module.id}/quiz`
    );
    expect(draw.ok()).toBeTruthy();

    const delivered = await request.get(`${API}/v1/sessions/${sessionId}/learning/checkins`);
    expect(delivered.ok()).toBeTruthy();
    const body = await delivered.json();
    expect(['quiz_active', 'none', 'cooldown']).toContain(body.gate);
    expect(body.item ?? null).toBeNull();
  });

  test('the dashboard is reachable from the learning hub', async ({ page, request }) => {
    const { sessionId } = await seedSessionViaApi(request);
    await openLearningHub(page, sessionId);
    await expect(page.getByRole('heading', { name: 'Your learning path' })).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole('link', { name: /progress/i }).click();
    await expect(page.getByRole('heading', { name: 'Progress', level: 1 })).toBeVisible({
      timeout: 30_000,
    });
    await expectAxeClean(page);
  });
});
