// Capture the conversation state (bubbles, kind labels, chips) for visual
// regression review. Usage: node scripts/screenshot_conversation.mjs <outDir>
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const outDir = process.argv[2] || 'eval/screenshots/conversation';
mkdirSync(outDir, { recursive: true });

const WEB = process.env.WEB_BASE_URL || 'http://127.0.0.1:3000';
const API = process.env.API_BASE_URL || 'http://127.0.0.1:8000';

const created = await fetch(`${API}/v1/sessions`, { method: 'POST' });
if (!created.ok) throw new Error(`session create failed: ${created.status}`);
const { session_id } = await created.json();

const browser = await chromium.launch();
for (const vp of [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1280, height: 900 },
]) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  await page.addInitScript(
    ([key, value]) => window.localStorage.setItem(key, value),
    ['scratly.student.session_id', session_id]
  );
  await page.goto(WEB, { waitUntil: 'networkidle' });
  await page.getByLabel('Your message').waitFor({ state: 'visible', timeout: 30_000 });
  await page
    .getByLabel('Your message')
    .fill('I like building small science projects with neighborhood air quality data and a couple of friends.');
  await page.getByRole('button', { name: 'Send' }).click();
  await page
    .locator('.chat-bubble.assistant:not(.working)')
    .first()
    .waitFor({ timeout: 120_000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(outDir, `conversation-${vp.name}.png`), fullPage: true });
  console.log(`saved conversation-${vp.name}.png`);
  await page.close();
}
await browser.close();
