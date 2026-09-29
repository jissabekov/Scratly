import { expect, test, type Page } from '@playwright/test';
import { API, axeViolations, openSeededSession, seedSessionViaApi } from './helpers';

async function expectChatReady(page: Page) {
  const composer = page.getByLabel('Your message');
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  return composer;
}

test.describe('Seeded session resume + accessibility', () => {
  test('hydrates a session created via the API and passes axe on the chat', async ({
    page,
    request,
  }) => {
    const health = await request.get(`${API}/health`);
    expect(health.ok(), 'API /health must be up').toBeTruthy();

    const { sessionId, stage } = await seedSessionViaApi(request);
    expect(stage).toBe('discovery');

    await openSeededSession(page, sessionId);
    const composer = await expectChatReady(page);

    // The stored session id must survive the boot (no new session created).
    const stored = await page.evaluate(() =>
      window.localStorage.getItem('scratly.student.session_id')
    );
    expect(stored).toBe(sessionId);
    await expect(page.locator('.chat-bubble.welcome')).toBeVisible();
    await expect(page.locator('.stage-chip')).toContainText(/Discovery/i);

    // Server state backs the DOM: the same session is discoverable via the API.
    const resume = await request.get(`${API}/v1/sessions/${sessionId}`);
    expect(resume.ok()).toBeTruthy();
    const resumeBody = await resume.json();
    expect(resumeBody.session_id).toBe(sessionId);
    expect(resumeBody.stage).toBe('discovery');

    // Accessibility: the booted chat must be axe-clean (WCAG 2.2 AA tags).
    const violations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
    expect(
      violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
    ).toEqual([]);

    // One live turn keeps the page accessible too.
    await composer.fill('I like building small science projects with air quality data.');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect
      .poll(async () => page.locator('.chat-bubble.assistant:not(.working)').count(), {
        timeout: 120_000,
      })
      .toBeGreaterThan(0);
    await expect(page.locator('.chat-bubble.working')).toHaveCount(0);

    const afterViolations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
    expect(
      afterViolations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
    ).toEqual([]);
  });

  test('teacher console passes axe after loading a session', async ({ page, request }) => {
    const { sessionId } = await seedSessionViaApi(request);

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
    await expect(page.locator('#Profile')).toBeVisible({ timeout: 30_000 });

    const violations = await axeViolations(page, ['wcag2a', 'wcag2aa', 'wcag22aa']);
    expect(
      violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join('; ')}`)
    ).toEqual([]);
  });

  test('teacher console deep-links a session via ?session=', async ({ page, request }) => {
    const { sessionId } = await seedSessionViaApi(request);

    // Deep-link straight to the session: no select interaction required.
    await page.goto(`/teacher?session=${sessionId}`);
    await expect(page.getByRole('heading', { name: 'Student assessment console' })).toBeVisible();
    await expect(page.locator('select')).toHaveValue(sessionId, { timeout: 30_000 });
    await expect(page.locator('#Profile')).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('#Profile .item-list li').first()).toBeVisible({ timeout: 30_000 });
    expect(new URL(page.url()).searchParams.get('session')).toBe(sessionId);

    // Selecting a different session keeps the URL in sync (deep-linkable).
    const other = await seedSessionViaApi(request);
    await page.getByRole('button', { name: 'Refresh' }).click();
    await expect
      .poll(async () => {
        const options = await page.locator('select option').allTextContents();
        return options.some((t) => t.includes(other.sessionId.slice(0, 8)));
      }, { timeout: 30_000 })
      .toBeTruthy();
    await page.locator('select').selectOption({ value: other.sessionId });
    await expect
      .poll(() => new URL(page.url()).searchParams.get('session'), { timeout: 30_000 })
      .toBe(other.sessionId);
  });
});
