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
