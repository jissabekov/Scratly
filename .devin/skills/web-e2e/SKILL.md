---
name: web-e2e
description: Run and extend Scratly Playwright e2e tests (student chat, teacher console, future learning flows)
allowed-tools:
  - exec
  - read
  - grep
  - glob
---

Setup: API on :8000 (`cd apps/api && ../../.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`) + Postgres (`docker compose up -d --wait postgres`).

Run: `npm --prefix apps/web run test:e2e` (config: `apps/web/playwright.config.ts`; API target via `API_BASE_URL`).

Conventions (from `apps/web/e2e/student-chat.spec.ts`):
- Seed state through the API (`request.post('/v1/sessions')`), never through UI setup loops.
- Deep-link flows via URL params (`?slide=`, `?q=`) — tests must not depend on click-paths for positioning.
- Session id lives in `localStorage['scratly.student.session_id']`; clear it for a fresh session.
- Assistant replies are async (LLM) — use `expect.poll` with generous timeouts, never fixed sleeps.
- Teacher console checks: select session by id prefix, poll for content.
- Adding a test for a new flow: mirror the existing describe/test structure; assert server state (messages/projects endpoints) as well as DOM; never edit assertions to make a broken flow pass.

Plan 08 Back cases (add these; the existing history test stays):
- Assert a visible route-level Back control: the hub returns to chat, progress returns to the hub with the same `session` query, slide 1 and quiz question 1 return to the parent route, and teacher returns to chat.
- Keep `page.goBack()` in `e2e/learning.spec.ts`. From slide 2, the button named Back returns to slide 1, and a later `goBack()` assertion still holds for browser history.
- `.agents/skills/web-design-guidelines/SKILL.md` is the review checklist. Playwright is the proof. Never weaken an assertion to make a broken flow pass.
