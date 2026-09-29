// Baseline screenshot capture for visual regression (Plan 02 W2.5).
// Usage: node scripts/screenshot_baseline.mjs [outDir]
// Requires the web dev server on :3000 and the API on :8000.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

const outDir = process.argv[2] || 'eval/screenshots/baseline';
mkdirSync(outDir, { recursive: true });

const BASE = process.env.WEB_BASE_URL || 'http://127.0.0.1:3000';
const VIEWPORTS = [
  { name: 'mobile', width: 390, height: 844 },
  { name: 'desktop', width: 1280, height: 800 },
];

const browser = await chromium.launch();
for (const vp of VIEWPORTS) {
  const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(outDir, `home-${vp.name}.png`), fullPage: true });
  console.log(`saved home-${vp.name}.png`);
  await page.close();
}
await browser.close();
