---
name: frontend-ui
description: Build or modify Scratly web UI (Next.js 15/React 19) following the lesson-player, quiz, and chat component conventions
allowed-tools:
  - read
  - edit
  - grep
  - glob
  - exec
---

Process: brainstorm → explore existing components → plan → implement → critique → critique again (visual + a11y).

Rules:
1. Read `apps/web/AGENTS.md` first — it is binding (server components default, Server Actions for mutations, URL-param flow state, Tailwind v4 + existing tokens, lucide icons, Motion transitions).
2. One idea per slide/screen; fixed bottom action bar (`FlowActionBar` pattern: Back ghost + primary CTA); immediate feedback with explanation, never silent advance.
3. Reuse `components/ui/` (shadcn generated — never hand-edit); new components under `components/<domain>/`.
4. A11y contract before marking done: focus-to-heading on step change, "Step x of n" live region, fieldset/legend + radiogroup semantics, aria-current steppers, full keyboard path (←/→, 1–4, Enter), AA contrast.
5. Respect `prefers-reduced-motion` for all Motion animations; celebrations only at milestones.
6. Verify: `npm --prefix apps/web run build` + affected Playwright specs (`/web-e2e`); never weaken an e2e assertion to pass.
7. Visual polish loop: run the dev server, screenshot the flow at mobile (390px) and desktop (1280px) widths, critique spacing/typography/hierarchy against the token system, iterate.
