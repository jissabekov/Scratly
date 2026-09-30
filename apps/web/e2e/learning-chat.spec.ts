import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import { API, SESSION_KEY, axeViolations, openSeededSession } from './helpers';

/**
 * Plan 06 §6.2/§6.4 — the per-session learning seam, chat terminal routing, and
 * the check-in write key.
 *
 * All state is seeded through the API (the only state authority); the chat is
 * never driven through UI setup loops. The terminal routing branch is checked
 * defensively: reaching `stage === 'complete'` needs the full multi-turn LLM
 * assessment + project matching, and no API endpoint sets
 * `core.sessions.matching_completed`, so the live e2e path exercises the
 * *negative* half of the contract (see the comment on the routing test).
 */

type SessionCreated = {
  session_id: string;
  student_id: string;
  stage: string;
  learning_enabled: boolean;
};

type Hub = {
  session_id: string;
  archetype_key: string;
  modules: { id: string; title: string; seq: number; state: string; slides_total: number }[];
};

type Detail = {
  module: { id: string; title: string };
  slides: { id: string; index: number; completed: boolean }[];
  quiz: { available: boolean };
};

type CheckinDeliver = {
  session_id: string;
  gate: string;
  item: {
    id: string;
    objective_code: string;
    objective_label: string;
    kind: string;
    prompt: string;
    trigger_reason: string;
    scale: { min: number; max: number; low_label: string; high_label: string } | null;
    options: { key: string; label: string }[];
  } | null;
  retry_after_seconds: number | null;
  event_id: string | null;
  checkins_used: number;
  max_checkins: number;
};

type TurnResponse = {
  turn_id: string;
  assistant_message: string;
  stage: string;
  message_kind: string | null;
  elicitation: unknown;
  learning: CheckinDeliver | null;
  student_message_id: string | null;
  assistant_message_id: string | null;
};

const STUDENT_TEXT =
  'I like building small science projects with neighborhood air quality data and a couple of friends.';

/** Unique idempotency/request key (API requires >= 8 chars). */
function rid(tag: string): string {
  return `e2e-${tag}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

async function createSession(
  request: APIRequestContext,
  learningEnabled: boolean | undefined
): Promise<SessionCreated> {
  const response =
    learningEnabled === undefined
      ? await request.post(`${API}/v1/sessions`)
      : await request.post(`${API}/v1/sessions`, {
          data: { learning_enabled: learningEnabled },
        });
  expect(response.ok(), 'POST /v1/sessions must succeed').toBeTruthy();
  return response.json();
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

/** Complete the first `count` slides of the module through the API. */
async function completeSlides(
  request: APIRequestContext,
  sessionId: string,
  detail: Detail,
  count: number
): Promise<void> {
  for (const slide of detail.slides.slice(0, count)) {
    const response = await request.post(
      `${API}/v1/sessions/${sessionId}/learning/slides/${slide.id}/complete`,
      { data: { request_id: rid(`slide-${slide.index}`), time_on_slide_ms: 4000 } }
    );
    expect(response.ok(), `completing slide ${slide.index} must succeed`).toBeTruthy();
  }
}

async function postTurn(
  request: APIRequestContext,
  sessionId: string,
  text: string
): Promise<TurnResponse> {
  const response = await request.post(`${API}/v1/sessions/${sessionId}/turns`, {
    data: { idempotency_key: rid('turn'), text },
    timeout: 120_000,
  });
  expect(response.ok(), 'POST /v1/sessions/{id}/turns must succeed').toBeTruthy();
  return response.json();
}

/** Seed a learning-enabled session with two completed slides; return its id. */
async function seedLearningSessionWithSlides(request: APIRequestContext): Promise<string> {
  const created = await createSession(request, true);
  expect(created.learning_enabled).toBe(true);
  const hub = await fetchHub(request, created.session_id);
  const detail = await fetchDetail(request, created.session_id, hub.modules[0].id);
  await completeSlides(request, created.session_id, detail, 2);
  return created.session_id;
}

async function expectAxeClean(page: Page) {
  const violations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
  expect(
    violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
  ).toEqual([]);
}

test.describe('Learning chat routing and check-ins', () => {
  test('a learning-enabled session is opt-in and keeps chat on the assessment path until terminal', async ({
    request,
  }) => {
    // Contract 1 — the per-session learning seam.
    const enabled = await createSession(request, true);
    expect(enabled.learning_enabled).toBe(true);
    const sessionId = enabled.session_id;

    const resumed = await request.get(`${API}/v1/sessions/${sessionId}`);
    expect(resumed.ok(), 'GET /v1/sessions/{id} must succeed').toBeTruthy();
    expect((await resumed.json()).learning_enabled).toBe(true);

    const messages = await request.get(`${API}/v1/sessions/${sessionId}/messages`);
    expect(messages.ok(), 'GET /v1/sessions/{id}/messages must succeed').toBeTruthy();
    expect((await messages.json()).learning_enabled).toBe(true);

    // Default is false (staged rollout, W6.5).
    const defaulted = await createSession(request, undefined);
    expect(defaulted.learning_enabled).toBe(false);

    // Real learning activity: two slides completed in the first module.
    const hub = await fetchHub(request, sessionId);
    const detail = await fetchDetail(request, sessionId, hub.modules[0].id);
    await completeSlides(request, sessionId, detail, 2);

    // Contract 2 — chat terminal routing. A learning-active but NON-terminal
    // session must not surface a learning payload. Reaching `stage === 'complete'`
    // requires the whole discovery -> profile_review -> project_matching flow
    // (which flips `core.sessions.matching_completed`) and there is no API
    // endpoint to force it, so this live e2e run asserts the negative half of
    // the contract; the positive shape is pinned below for the terminal case.
    const turn = await postTurn(request, sessionId, STUDENT_TEXT);

    if (turn.message_kind === 'progress_checkin') {
      // Terminal routing contract: the payload mirrors the check-in deliver
      // response. Only reachable once the session is terminal.
      expect(turn.learning, 'progress_checkin must carry a learning payload').not.toBeNull();
      const learning = turn.learning!;
      expect(learning.session_id).toBe(sessionId);
      expect(typeof learning.gate).toBe('string');
      expect(learning.item, 'a delivered check-in must include an item').not.toBeNull();
      expect(learning.event_id, 'a delivered check-in must expose its event id').toBeTruthy();
      expect(learning.checkins_used).toBeGreaterThanOrEqual(1);
      expect(learning.max_checkins).toBeGreaterThanOrEqual(1);
      expect(learning.item!.objective_code).toBeTruthy();
      expect(learning.item!.objective_label).toBeTruthy();
      expect(learning.item!.kind).toBeTruthy();
      expect(learning.item!.prompt).toBeTruthy();
      expect(learning.item!.trigger_reason).toBeTruthy();
      expect(learning.item!.scale !== null || learning.item!.options.length > 0).toBeTruthy();
    } else {
      expect(turn.stage, 'a non-terminal session must not report complete').not.toBe(
        'complete'
      );
      expect(turn.learning, 'no learning payload before the terminal path').toBeNull();
      expect(turn.message_kind).not.toBe('progress_checkin');
      expect([
        'assessment_question',
        'student_answer',
        'refusal',
        'elicitation',
        'profile_review',
        'matching_unavailable',
      ]).toContain(turn.message_kind);
    }
  });

  test('the chat renders an inline check-in card only when the terminal path delivers one', async ({
    page,
    request,
  }) => {
    const sessionId = await seedLearningSessionWithSlides(request);

    // Decide the routing through the API so the branch is explicit.
    const turn = await postTurn(request, sessionId, STUDENT_TEXT);

    await openSeededSession(page, sessionId);
    // The bootstrap resolves the seeded session id from localStorage.
    await expect
      .poll(() => page.evaluate((key) => window.localStorage.getItem(key), SESSION_KEY))
      .toBe(sessionId);
    await expect(page.getByLabel('Your message')).toBeEnabled({ timeout: 30_000 });

    const completionPanel = page.locator('.chat-complete');
    const checkinCard = page.locator('[aria-labelledby="checkin-heading"]');

    if (turn.message_kind === 'progress_checkin') {
      const item = turn.learning!.item!;
      // The inline card is rendered from the live turn response. Reload the
      // seeded session (session id from localStorage) and assert it is present.
      await openSeededSession(page, sessionId);
      const card = page.getByRole('region').filter({ hasText: /quick check-in/i });
      await expect(card).toBeVisible({ timeout: 30_000 });
      await expect(page.getByRole('heading', { name: item.prompt })).toBeVisible();
      const submit = card.getByRole('button', { name: 'Submit' });
      await expect(submit).toBeVisible();

      // Answer it (likert -> pick the low value; mcq -> pick an option).
      if (item.kind === 'likert' && item.scale) {
        await card.getByRole('radio', { name: String(item.scale.min) }).click();
      } else if (item.kind === 'mcq' && item.options.length > 0) {
        await card.getByRole('radio').first().click();
      } else {
        await card.getByRole('textbox').fill('In my own words.');
      }
      await expect(submit).toBeEnabled();
      await submit.click();
      await expect(card.getByRole('status')).toContainText(/Thanks|saved/i, {
        timeout: 30_000,
      });
      // The completion panel stays hidden while a learning journey is active.
      await expect(completionPanel).toHaveCount(0);
    } else {
      // Terminal state is unreachable through the live API surface (no endpoint
      // sets `matching_completed`), so assert the negative: an active learning
      // journey must NOT surface a check-in card here and must NOT show the
      // "That's a wrap" completion panel (the terminal path stays terminal for
      // assessment, but learning keeps the thread conversational).
      await expect(page.locator('.chat-bubble.assistant:not(.working)').first()).toBeVisible({
        timeout: 30_000,
      });
      await expect(checkinCard).toHaveCount(0);
      await expect(completionPanel).toHaveCount(0);
      await expectAxeClean(page);
    }
  });

  test('the check-in write key is the event id, not the item id (regression guard)', async ({
    request,
  }) => {
    const sessionId = await seedLearningSessionWithSlides(request);

    const delivered = await request.get(
      `${API}/v1/sessions/${sessionId}/learning/checkins`
    );
    expect(delivered.ok(), 'GET learning check-ins must succeed').toBeTruthy();
    const body: CheckinDeliver = await delivered.json();
    expect(body.gate, 'a fresh session with section activity delivers a check-in').toBe(
      'available'
    );
    expect(body.item, 'a delivered check-in must include an item').not.toBeNull();
    expect(body.event_id, 'a delivered check-in must expose an event id').toBeTruthy();
    expect(body.event_id).not.toBe(body.item!.id);

    const answer = (requestId: string) => ({
      request_id: requestId,
      response: [] as string[],
      free_text: 'event-id guard probe',
    });

    // The event id is the write key.
    const byEvent = await request.post(
      `${API}/v1/sessions/${sessionId}/learning/checkins/${body.event_id}`,
      { data: answer(rid('by-event')) }
    );
    expect(byEvent.status(), 'POST .../checkins/{event_id} must be accepted').toBe(200);

    // The item id is not an event id — it must 404, pinning the fix.
    const byItem = await request.post(
      `${API}/v1/sessions/${sessionId}/learning/checkins/${body.item!.id}`,
      { data: answer(rid('by-item')) }
    );
    expect(byItem.status(), 'POST .../checkins/{item.id} must 404').toBe(404);
  });

  test('the chat surface is axe-clean in a learning-active session', async ({
    page,
    request,
  }) => {
    const sessionId = await seedLearningSessionWithSlides(request);
    await openSeededSession(page, sessionId);
    await expect(page.getByLabel('Your message')).toBeEnabled({ timeout: 30_000 });
    await expect(page.getByRole('heading', { name: 'Scratly' })).toBeVisible();
    await expectAxeClean(page);
  });
});
