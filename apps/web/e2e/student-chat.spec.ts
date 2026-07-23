import { expect, test, type Page } from '@playwright/test';

const API = process.env.API_BASE_URL || 'http://127.0.0.1:8000';

async function sessionIdFromPage(page: Page): Promise<string> {
  const id = await page.evaluate(() =>
    window.localStorage.getItem('scratly.student.session_id')
  );
  expect(id, 'session id should be stored in localStorage').toBeTruthy();
  return id as string;
}

async function waitForAssistantReply(page: Page, afterCount: number) {
  const replies = page.locator('.chat-bubble.assistant:not(.working)');
  await expect
    .poll(async () => replies.count(), {
      timeout: 120_000,
    })
    .toBeGreaterThan(afterCount);
}

test.describe('Student chat conversation', () => {
  test('creates session, exchanges turns, persists transcript, resumes after reload', async ({
    page,
    request,
  }) => {
    const health = await request.get(`${API}/health`);
    expect(health.ok(), 'API /health must be up').toBeTruthy();

    await page.goto('/');
    await page.evaluate(() => window.localStorage.removeItem('scratly.student.session_id'));
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Scratly' })).toBeVisible();
    await expect(page.locator('.chat-bubble.welcome')).toContainText(
      'When nobody'
    );
    await expect(page.locator('.stage-chip')).toContainText(/Discovery/i);

    // Wait until session boot finishes (composer enabled).
    const composer = page.getByLabel('Your message');
    await expect(composer).toBeEnabled({ timeout: 30_000 });

    const sessionId = await sessionIdFromPage(page);

    const before = await request.get(`${API}/v1/sessions/${sessionId}/messages`);
    expect(before.ok()).toBeTruthy();
    const beforeBody = await before.json();
    expect(beforeBody.items).toEqual([]);
    expect(beforeBody.stage).toBe('discovery');

    const studentText =
      'I like building small science projects with neighborhood air quality data and a couple of friends.';
    await composer.fill(studentText);
    await page.getByRole('button', { name: 'Send' }).click();

    await expect(page.locator('.chat-bubble.student').filter({ hasText: studentText })).toBeVisible();
    await waitForAssistantReply(page, 0);

    const assistantBubbles = page.locator('.chat-bubble.assistant:not(.working)');
    await expect(assistantBubbles.first()).toBeVisible();
    const assistantText = (await assistantBubbles.first().locator('p').innerText()).trim();
    expect(assistantText.length).toBeGreaterThan(15);
    // Working indicator should clear after reply
    await expect(page.locator('.chat-bubble.working')).toHaveCount(0);

    const afterTurn = await request.get(`${API}/v1/sessions/${sessionId}/messages`);
    expect(afterTurn.ok()).toBeTruthy();
    const stored = await afterTurn.json();
    expect(stored.items.length).toBeGreaterThanOrEqual(2);
    expect(stored.items[0].role).toBe('student');
    expect(stored.items[0].content).toContain('neighborhood');
    expect(stored.items[1].role).toBe('assistant');
    expect(stored.items[1].content.length).toBeGreaterThan(5);
    expect(stored.items[1].message_kind).toBeTruthy();

    const resumeMeta = await request.get(`${API}/v1/sessions/${sessionId}`);
    expect(resumeMeta.ok()).toBeTruthy();
    const resumeBody = await resumeMeta.json();
    expect(resumeBody.session_id).toBe(sessionId);
    expect(typeof resumeBody.stage).toBe('string');

    // Second turn
    const followUp =
      'No hard budget limit, but I am based in Seattle and prefer small group work.';
    await composer.fill(followUp);
    await page.getByRole('button', { name: 'Send' }).click();
    await waitForAssistantReply(page, 1);

    const afterTwo = await request.get(`${API}/v1/sessions/${sessionId}/messages`);
    const two = await afterTwo.json();
    expect(two.items.length).toBeGreaterThanOrEqual(4);
    const roles = two.items.map((m: { role: string }) => m.role);
    expect(roles.filter((r: string) => r === 'student').length).toBeGreaterThanOrEqual(2);
    expect(roles.filter((r: string) => r === 'assistant').length).toBeGreaterThanOrEqual(2);

    // Reload should restore DB transcript (welcome gone once messages exist)
    await page.reload();
    await expect(composer).toBeEnabled({ timeout: 30_000 });
    await expect(page.locator('.chat-bubble.student').filter({ hasText: studentText })).toBeVisible();
    await expect(page.locator('.chat-bubble.student').filter({ hasText: 'Seattle' })).toBeVisible();
    await expect(page.locator('.chat-bubble.assistant:not(.working)').first()).toBeVisible();
    const resumedId = await sessionIdFromPage(page);
    expect(resumedId).toBe(sessionId);

    // Teacher console can see the same session
    await page.goto('/teacher');
    await expect(page.getByRole('heading', { name: 'Student assessment console' })).toBeVisible();
    const select = page.locator('select');
    await expect
      .poll(async () => {
        const options = await select.locator('option').allTextContents();
        return options.some((t) => t.includes(sessionId.slice(0, 8)));
      }, { timeout: 30_000 })
      .toBeTruthy();
    await select.selectOption({ value: sessionId });
    await expect(page.locator('#Conversation')).toBeVisible();
    await expect
      .poll(async () => page.locator('#Conversation .item-list li').count(), {
        timeout: 30_000,
      })
      .toBeGreaterThanOrEqual(4);
  });

  test('New chat creates a fresh session id', async ({ page, request }) => {
    await page.goto('/');
    await page.evaluate(() => window.localStorage.removeItem('scratly.student.session_id'));
    await page.reload();
    const composer = page.getByLabel('Your message');
    await expect(composer).toBeEnabled({ timeout: 30_000 });
    const first = await sessionIdFromPage(page);

    await page.getByRole('button', { name: 'New chat' }).click();
    await expect(composer).toBeEnabled({ timeout: 30_000 });
    await expect(page.locator('.chat-bubble.welcome')).toBeVisible();

    const second = await sessionIdFromPage(page);
    expect(second).not.toBe(first);

    const a = await request.get(`${API}/v1/sessions/${first}`);
    const b = await request.get(`${API}/v1/sessions/${second}`);
    expect(a.ok()).toBeTruthy();
    expect(b.ok()).toBeTruthy();
  });
});
