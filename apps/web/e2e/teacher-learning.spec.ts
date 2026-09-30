import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { API, axeViolations } from './helpers';

/**
 * Plan 06 §6.4/§6.6 — the teacher console's three learning views.
 *
 * `apps/web/app/teacher/page.tsx` renders every admin view through one generic
 * table; this spec seeds a real learning journey through the API (slides, one
 * quiz attempt, one answered check-in), then asserts both the admin read models
 * (`/v1/admin/sessions/{id}/{view}` -> `{session_id, view, items}`) and the DOM
 * rows, with an axe pass over the console.
 */

type Hub = {
  session_id: string;
  modules: { id: string; title: string; seq: number; state: string }[];
};

type Detail = {
  module: { id: string; title: string };
  slides: { id: string; index: number }[];
};

type QuizDraw = {
  gate: string;
  attempt: { attempt_id: string; items: { id: string }[] } | null;
};

type CheckinDeliver = {
  gate: string;
  item: {
    id: string;
    kind: string;
    scale: { min: number; max: number } | null;
    options: { key: string }[];
  } | null;
  event_id: string | null;
};

type AdminView = {
  session_id: string;
  view: string;
  items: Record<string, unknown>[];
};

function rid(tag: string): string {
  return `e2e-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

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

async function getView(
  request: APIRequestContext,
  sessionId: string,
  view: string
): Promise<AdminView> {
  const response = await request.get(`${API}/v1/admin/sessions/${sessionId}/${view}`);
  expect(response.ok(), `GET admin view ${view} must succeed`).toBeTruthy();
  return response.json();
}

async function expectAxeClean(page: Page) {
  const violations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
  expect(
    violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
  ).toEqual([]);
}

/**
 * Seed a learning journey for the teacher views: create an opt-in session,
 * complete two slides, submit one (failing) quiz attempt, and answer one
 * delivered check-in. Returns the session id and the first module title.
 */
async function seedLearningJourney(
  request: APIRequestContext
): Promise<{ sessionId: string; moduleTitle: string }> {
  // Opt the session into the learning journey through the documented seam
  // (mirrors the `seedSessionViaApi` convention, with the rollout flag set).
  const created = await request.post(`${API}/v1/sessions`, {
    data: { learning_enabled: true },
  });
  expect(created.ok(), 'POST /v1/sessions (learning_enabled) must succeed').toBeTruthy();
  const learningSessionId: string = (await created.json()).session_id;

  const hub = await fetchHub(request, learningSessionId);
  const firstModule = hub.modules[0];
  const detail = await fetchDetail(request, learningSessionId, firstModule.id);
  expect(detail.slides.length, 'the first module must have slides').toBeGreaterThan(1);

  // Complete two slides (real learning activity -> progress + module row).
  for (const slide of detail.slides.slice(0, 2)) {
    const response = await request.post(
      `${API}/v1/sessions/${learningSessionId}/learning/slides/${slide.id}/complete`,
      { data: { request_id: rid(`slide-${slide.index}`), time_on_slide_ms: 4000 } }
    );
    expect(response.ok(), `completing slide ${slide.index} must succeed`).toBeTruthy();
  }

  // Draw and submit one quiz attempt (recorded in quiz-history, and it settles
  // the module's mastery rows in learning-progress).
  const drawResponse = await request.get(
    `${API}/v1/sessions/${learningSessionId}/learning/modules/${firstModule.id}/quiz`
  );
  expect(drawResponse.ok(), 'GET quiz draw must succeed').toBeTruthy();
  const draw: QuizDraw = await drawResponse.json();
  expect(draw.gate, 'the first module quiz must be reachable').toBe('available');
  expect(draw.attempt, 'the draw must return an attempt').not.toBeNull();
  const attempt = draw.attempt!;
  const submit = await request.post(
    `${API}/v1/sessions/${learningSessionId}/learning/quiz-attempts`,
    {
      data: {
        request_id: rid('quiz'),
        attempt_id: attempt.attempt_id,
        responses: attempt.items.map((item) => ({ item_id: item.id, response: [] })),
      },
    }
  );
  expect(submit.ok(), 'POST quiz attempt must succeed').toBeTruthy();

  // Answer one delivered check-in (learning evidence, never assessment).
  const deliverResponse = await request.get(
    `${API}/v1/sessions/${learningSessionId}/learning/checkins`
  );
  expect(deliverResponse.ok(), 'GET check-ins must succeed').toBeTruthy();
  const deliver: CheckinDeliver = await deliverResponse.json();
  expect(deliver.gate, 'a fresh session with section activity delivers a check-in').toBe(
    'available'
  );
  expect(deliver.item, 'the check-in must include an item').not.toBeNull();
  const item = deliver.item!;
  const answer =
    item.kind === 'mcq' && item.options.length > 0
      ? [item.options[0].key]
      : item.kind === 'likert' && item.scale
        ? [String(item.scale.min)]
        : [];
  const respond = await request.post(
    `${API}/v1/sessions/${learningSessionId}/learning/checkins/${deliver.event_id}`,
    { data: { request_id: rid('checkin'), response: answer, free_text: 'teacher view probe' } }
  );
  expect(respond.ok(), 'answering the check-in must succeed').toBeTruthy();

  return { sessionId: learningSessionId, moduleTitle: firstModule.title };
}

test.describe('Teacher learning views', () => {
  test('the console renders learning progress, quiz history, and interventions from live state', async ({
    page,
    request,
  }) => {
    const { sessionId, moduleTitle } = await seedLearningJourney(request);

    // Contract 5 — the admin read models return {session_id, view, items}.
    const progress = await getView(request, sessionId, 'learning-progress');
    expect(progress.session_id).toBe(sessionId);
    expect(progress.view).toBe('learning-progress');
    expect(
      progress.items.some((item) => item.row_kind === 'module'),
      'learning-progress must include the module row'
    ).toBe(true);
    expect(
      progress.items.filter((item) => item.row_kind === 'mastery').length,
      'learning-progress must include mastery rows after a quiz attempt'
    ).toBeGreaterThan(0);

    const history = await getView(request, sessionId, 'quiz-history');
    expect(history.session_id).toBe(sessionId);
    expect(history.view).toBe('quiz-history');
    expect(
      history.items.length,
      'quiz-history must include the submitted attempt'
    ).toBeGreaterThanOrEqual(1);

    const interventions = await getView(request, sessionId, 'interventions');
    expect(interventions.session_id).toBe(sessionId);
    expect(interventions.view).toBe('interventions');
    // No retention card (create_milestone_card is never invoked) and no advice
    // rung (only a scored mini_exercise/mcq check-in opens one, and the
    // deterministic kind mix never yields one at these ordinals) -> empty view.
    expect(interventions.items).toEqual([]);

    // DOM: the generic table renders the three new views.
    await page.goto(`/teacher?session=${sessionId}`);

    const progressArticle = page.locator('#Learning-progress');
    await expect(progressArticle).toBeVisible({ timeout: 30_000 });
    await expect(
      progressArticle.getByRole('heading', { name: 'Learning progress' })
    ).toBeVisible();
    await expect
      .poll(() => progressArticle.locator('.item-list li').count(), { timeout: 30_000 })
      .toBeGreaterThanOrEqual(2);
    await expect(progressArticle.getByText(moduleTitle).first()).toBeVisible();

    const historyArticle = page.locator('#Quiz-history');
    await expect(historyArticle).toBeVisible({ timeout: 30_000 });
    await expect(
      historyArticle.getByRole('heading', { name: 'Quiz history' })
    ).toBeVisible();
    await expect
      .poll(() => historyArticle.locator('.item-list li').count(), { timeout: 30_000 })
      .toBeGreaterThanOrEqual(1);

    const interventionsArticle = page.locator('#Interventions');
    await expect(interventionsArticle).toBeVisible({ timeout: 30_000 });
    await expect(
      interventionsArticle.getByRole('heading', { name: 'Interventions' })
    ).toBeVisible();
    await expect(
      interventionsArticle.getByText('No rows yet for this view')
    ).toBeVisible();
  });

  test('the teacher console is axe-clean with the learning views selected', async ({
    page,
    request,
  }) => {
    const { sessionId } = await seedLearningJourney(request);

    await page.goto(`/teacher?session=${sessionId}`);
    await expect(page.locator('#Learning-progress')).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(() => page.locator('#Learning-progress .item-list li').count(), {
        timeout: 30_000,
      })
      .toBeGreaterThanOrEqual(2);

    await expectAxeClean(page);
  });
});
