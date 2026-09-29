# Scratly Web — agent instructions (Next.js 15 App Router + React 19)

## Stack & commands

- next 15.1.4 / react 19 / TypeScript strict / npm. Dev: `npm --prefix apps/web run dev` · build: `npm --prefix apps/web run build` · e2e: `npm --prefix apps/web run test:e2e` (needs API on :8000 + Postgres).
- `next lint` is deprecated in 15.1+ — do not rely on it; typecheck via build.

## Architecture rules

- Server Components by default; `'use client'` only on interactive leaves (LessonPlayer, QuizRunner, CheckInWidget, chat components).
- All mutations via Server Actions (`lib/actions.ts`) that call FastAPI through `lib/api.ts` — **the API is the only state authority**; never persist progress/quiz/check-in state in localStorage (session id only, existing `lib/session.ts` pattern).
- Lesson/quiz position lives in URL search params (`?slide=`, `?q=`); transient UI state in `useReducer`/context inside the player only.
- `useActionState`/`useTransition` for pending + error UI; `<Suspense>` for slow data.

## Styling rules

- Tailwind v4 utilities; design tokens are the existing CSS custom properties (`--ink/--paper/--panel/--line/--accent/--muted/--warn` are canon — do not invent parallel names); global styles only in `@layer base`.
- `cn()` for conditional classes; shadcn/ui primitives for interactive controls; lucide icons only; Motion for transitions (always respect `prefers-reduced-motion`).
- Never mix CSS Modules and Tailwind on the same element.

## Component conventions

- `components/<domain>/<Component>.tsx`; `components/ui/` holds generated shadcn files — do not hand-edit.
- One component per file; `'use client'` as low in the tree as possible.
- Flows use the fixed bottom action bar pattern (Back ghost + primary CTA); a slide = one idea.

## Accessibility contract (non-negotiable for flows)

- Focus the step heading on transition; announce "Step x of n" via `role="status" aria-live="polite"`.
- `<fieldset>/<legend>` or `role="radiogroup"` per question; `aria-current="step"` on steppers; feedback in `aria-live`; full keyboard operability; WCAG 2.2 AA contrast on tokens.

## Boundaries

- **Always:** run build + affected e2e before claiming done; typecheck changed files; reuse existing tokens/components; keep diffs small.
- **Ask first:** new dependencies; changing FastAPI endpoints; new routes.
- **Never:** client-side progress persistence; `div onClick` interactive elements; inline styles duplicating tokens; editing e2e assertions to pass ("fake green"); sending student PII to the LLM.

## References

- `docs/plan/` (execution plans) · `docs/system-guide.md` · `playwright.config.ts`
- Skills: `/frontend-ui`, `/web-e2e`
