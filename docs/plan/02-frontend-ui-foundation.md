# Plan 02 — Frontend/UI foundation (Phase 2)

> **Status: READY (after Phase 1 fixes)** · Owner: Devin (frontend) · Depends on: Plan 01 (hygiene gates)
> **Goal:** upgrade `apps/web` from a single global stylesheet into a polished, accessible, agent-friendly UI foundation able to carry the learning journey (lesson player, quizzes, progress dashboard).

## 2.1 Architecture decisions (researched, with trade-offs)

| Decision | Choice | Rationale |
|---|---|---|
| Styling | **Tailwind CSS v4** + keep existing CSS custom-property tokens (`--ink/--paper/--panel/--line/--accent/--muted/--warn`) as the token layer | v4 is CSS-first (`@theme`, no config file), composes with the existing `:root` tokens, fastest route to teen-grade polish; best agent ecosystem (shadcn/cal.com/dub all standardize on it). Move `style.css` element selectors into `@layer base`; never mix CSS Modules and Tailwind on the same elements. |
| Components | **shadcn/ui (Radix primitives)**: Button, RadioGroup, Progress, Dialog, Tooltip, Card | Free WAI-ARIA compliance (roving-tabindex radio groups, focus management). shadcn's `Questionnaire` a11y contract is exactly our gated-quiz spec. Generated `ui/` files are not hand-edited. |
| Motion | **Motion (ex-framer-motion)** via `AnimatePresence` keyed slides | Documented slideshow recipe (direction-aware transitions); gate on `prefers-reduced-motion`. |
| Icons / celebration / charts | lucide-react · canvas-confetti (~3KB) · Recharts (dashboard only, code-split) | Module-path visualization is hand-rolled SVG/CSS (Duolingo-style), not a chart lib. |
| Rendering | **Server Components by default**; `'use client'` only on leaves (LessonPlayer, QuizRunner, CheckInWidget, chat components) | Current `app/page.tsx` is fully client — invert. |
| Mutations | **Server Actions** (`'use server'`) proxying FastAPI via `lib/api.ts`; `useActionState`/`useTransition` for pending/error | Backend stays the only state authority (mirrors "sole write path" hard rule); no client-side progress persistence ever. |
| Flow state | Lesson/quiz position in **URL search params** (`?slide=`, `?q=`) so refresh/back/deep-links work and Playwright can deep-link; transient UI state in `useReducer` inside the player | Testability + resumability. |
| Lint | Replace deprecated `next lint` with ESLint 9 flat config (next/core-web-vitals) | `next lint` is deprecated in 15.1+. |

## 2.2 Workstreams

**W2.1 — Tooling foundation:** add Tailwind v4 (`@tailwindcss/postcode` via `@import "tailwindcss"` + `@theme`), shadcn/ui init, `cn()` util, ESLint config; move global `style.css` into layered base; keep tokens canon (do not invent parallel names).
**W2.2 — Fix existing frontend debt:** `lib/types.ts` MessageKind union missing `matching_unavailable`/`post_match_feedback`; `MessageBubble` KIND_LABELS/CSS missing for those kinds (render unstyled today); `StudentChat` hard-blocks input at `stage==='complete'` (must relax for learning phase, Plan 06); `lib/types.ts` Stage union.
**W2.3 — Design system:** extend tokens (success/warning/info, motion durations, spacing scale); type roles (display/body/utility per Anthropic `frontend-design` skill guidance); dark-mode-ready token structure; AA contrast check on all pairs.
**W2.4 — Component primitives:** shadcn `ui/` generation (button, radio-group, progress, dialog, tooltip, card); `FlowActionBar` (fixed bottom: Back ghost + primary CTA — one shared component for slides AND quiz); `SlideProgress` (role=progressbar).
**W2.5 — E2E + visual regression:** Playwright conventions (deep-link via URL params, seeded sessions via API), screenshot review loop, axe accessibility assertions.

## 2.6 Accessibility contract (non-negotiable, goes into `apps/web/AGENTS.md`)

1. On slide/question transition, move focus to the step heading (`h2 tabindex="-1"`).
2. Announce "Step x of n" / "Question 2 of 5" via `role="status" aria-live="polite"`.
3. Back restores focus to trigger; feedback in `aria-live="polite"`; correct answer enables + focuses "Next".
4. `<fieldset>/<legend>` or `role="radiogroup"` per question; `aria-current="step"` on steppers; full keyboard operability (←/→ slides, 1–4 picks options); WCAG 2.2 AA contrast.

## 2.7 Acceptance

- `npm --prefix apps/web run build` green; existing 2 Playwright specs pass; new axe assertions pass.
- Chat UI visually unchanged or better (regression screenshots); tokens preserved.
- No new global-store dependency; no client-side progress persistence.

## 2.8 Skills created for frontend agents

- `.devin/skills/frontend-ui/SKILL.md` — component conventions, token rules, lesson-player patterns, a11y checklist.
- `.devin/skills/web-e2e/SKILL.md` — Playwright conventions for this repo.
- `apps/web/AGENTS.md` — nested always-on instructions (auto-loaded when Devin touches `apps/web/`).

## 2.9 Per-workstream status (2026-09-29)

Environment: Postgres up (migration `016_catalog_topic_buckets.sql` applied — 6 topic updates + 10 new catalog rows), API on :8000 with repo `.env` sourced, web dev on :3000. All gates run in-session.

| # | Workstream | Status | Evidence |
|---|---|---|---|
| W2.1 | Tooling foundation | **DONE** | Tailwind v4.3.3 CSS-first (`@import "tailwindcss"` + `@theme inline`, no config file) + `@tailwindcss/postcss` as sole plugin; `app/style.css` → `app/globals.css` with element selectors in `@layer base` and class selectors in `@layer components`; tokens canon verbatim; `cn()` in `lib/utils.ts`; ESLint 9 flat config (`eslint.config.mjs`, FlatCompat + `next/core-web-vitals`/`next/typescript`, `eslint-config-next` pinned to 15.1.4) replacing `next lint`; shadcn `ui/` primitives (button, radio-group, progress, dialog, tooltip, card). `eslint .` clean; build green. |
| W2.2 | Frontend debt | **DONE** | `MessageKind` gains `matching_unavailable` + `post_match_feedback` with KIND_LABELS and a dashed muted `unavailable` bubble variant; `Stage` union is now the exact 6-value enum (no `| string`); `StudentChat` no longer blocks input at `stage === 'complete'` (composer enabled, placeholder "Add a final note or question…") — the backend terminal fast path already answers post-match turns (`post_match_feedback_handled`), so no backend semantics changed. |
| W2.3 | Design system | **DONE** | Extended tokens: status (`--success/--warning/--info` + tints), motion (`--motion-fast/base/slow`), spacing (`--space-1…12`), `--line-strong` for WCAG 1.4.11 control boundaries, dark-mode-ready `.dark` block. `scripts/check_token_contrast.py` verifies every required pair in both modes — all pass AA (text ≥4.5:1, non-text ≥3:1); canon `--line` (decorative panel borders, exempt) reported as INFO. `--warning` darkened #8a6d1f → #755c17 (was 4.26:1 on paper). |
| W2.4 | Component primitives | **DONE** | `components/flow/FlowActionBar.tsx` (fixed bottom bar, Back ghost + primary CTA, `aria-busy` pending state) and `components/flow/SlideProgress.tsx` (Radix progressbar + visible "Step x of n" polite live region). Both are the shared primitives Phase 3/4 players consume. |
| W2.5 | E2E + visual regression | **DONE** | `e2e/helpers.ts` (API session seeding, localStorage seeding, axe helper); new `e2e/session-resume.spec.ts` (hydration + server-state parity + `?session=` deep-link); axe WCAG 2.2 AA assertions added to the booted chat, live transcript, and teacher console. **5/5 Playwright specs pass** (43.7 s). Screenshot loop: `apps/web/scripts/screenshot_baseline.mjs` + `screenshot_conversation.mjs`; baseline vs after shows the chat visually unchanged apart from the intended stronger input border. |

Deferred (recorded, not dropped): the `?slide=` / `?q=` deep-link specs belong to the lesson/quiz players and attach in Phase 3 — those URL params do not exist yet. W2.5's deep-link convention is proven today via the teacher console `?session=` param (UI-only, no backend change).

Non-negotiables honoured: tokens preserved verbatim (only additions + the `--warning` AA fix), no new global-store dependency, no client-side progress persistence, chat UI visually unchanged or better.
